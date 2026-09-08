"""
Assembles parsed script Segments into final per-test MP3 files:

  turns -> per-line TTS clips -> section track (with gaps + true silence)
        -> ambience overlay (skipped under the 30s silence)
        -> section files concatenated (with short crossfade) -> Test_N.mp3

Every synthesize_line call is given a voice_id resolved from a per-test
voice_map (speaker -> voice_id), built once by voice_assignment.py at the
start of build_test_audio() so each speaker's voice is randomized but
stays fixed for the whole test -- see voice_assignment.py.
"""

from __future__ import annotations

import os
import random

from pydub import AudioSegment
from pydub.generators import WhiteNoise

import config
import tts_client
import voice_assignment
from parser import Segment


def _generate_ambience_bed(duration_ms: int, seed: int = 0) -> AudioSegment:
    """
    Very soft, low-passed white-noise bed as a stand-in room-tone. Replace
    with a real recorded ambience track in ./ambience/<name>.wav for
    production use (see config.AMBIENCE_DESCRIPTIONS for the brief).
    """
    random.seed(seed)
    noise = WhiteNoise().to_audio_segment(duration=duration_ms + 1000)
    # crude low-pass by downsampling and back up, softens the hiss
    noise = noise.set_frame_rate(4000).set_frame_rate(44100)
    noise = noise.apply_gain(-40)
    return noise[:duration_ms]


def _load_or_generate_ambience(section_num: int, duration_ms: int) -> AudioSegment:
    path = os.path.join(config.AMBIENCE_DIR, f"section{section_num}.wav")
    if os.path.exists(path):
        bed = AudioSegment.from_file(path)
        if len(bed) < duration_ms:
            loops = duration_ms // len(bed) + 1
            bed = bed * loops
        return bed[:duration_ms]
    return _generate_ambience_bed(duration_ms, seed=section_num)


def _voice_for(turn, voice_map: dict) -> str:
    key = turn.speaker or "NARRATOR"
    if key in voice_map:
        return voice_map[key]
    # Shouldn't happen (voice_map is built from the same turns beforehand),
    # but resolve on the fly rather than crash if it ever does.
    fallback = voice_assignment.assign_test_voices([key])
    return fallback[key]


def build_segment_track(segment: Segment, cache_dir: str, voice_map: dict) -> AudioSegment:
    """Concatenate all turns in one Segment (one original 'file') into audio."""
    track = AudioSegment.silent(duration=0)
    for turn in segment.turns:
        if turn.kind == "silence":
            track += AudioSegment.silent(duration=turn.ms or config.SILENCE_MARKER_MS)
            continue

        clip = tts_client.synthesize_line(
            text=turn.text, voice_id=_voice_for(turn, voice_map), tag=turn.tag, cache_dir=cache_dir
        )
        track += clip
        gap = config.GAP_AFTER_NARRATOR_MS if turn.kind == "narrator" else config.GAP_BETWEEN_TURNS_MS
        track += AudioSegment.silent(duration=gap)
    return track


def build_section_audio(section_num: int, segments: list, cache_dir: str, voice_map: dict) -> AudioSegment:
    """
    Build one full IELTS section (Intro -> Part1 -> Transition[+30s silence]
    -> Part2 -> End), overlaying subtle ambience under speech but never
    under the scored 30-second silence gap (per the QC checklist in the
    source scripts).
    """
    section_track = AudioSegment.silent(duration=0)

    for seg in segments:
        # Build this file-segment turn-by-turn so we can withhold ambience
        # specifically during silence turns.
        seg_audio = AudioSegment.silent(duration=0)
        for turn in seg.turns:
            if turn.kind == "silence":
                seg_audio += AudioSegment.silent(duration=turn.ms or config.SILENCE_MARKER_MS)
                continue
            clip = tts_client.synthesize_line(
                text=turn.text, voice_id=_voice_for(turn, voice_map), tag=turn.tag, cache_dir=cache_dir
            )
            # Ambience under this individual line only (not under silence turns)
            bed = _load_or_generate_ambience(section_num, len(clip))
            bed = bed.apply_gain(config.AMBIENCE_DB_RELATIVE)
            spoken = clip.overlay(bed)
            seg_audio += spoken
            gap = config.GAP_AFTER_NARRATOR_MS if turn.kind == "narrator" else config.GAP_BETWEEN_TURNS_MS
            gap_audio = AudioSegment.silent(duration=gap)
            # ambient hum continues softly through the natural pause too
            gap_bed = _load_or_generate_ambience(section_num, gap).apply_gain(config.AMBIENCE_DB_RELATIVE - 4)
            seg_audio += gap_audio.overlay(gap_bed)

        section_track += seg_audio

    return section_track


def build_section_audio_dry(section_num: int, segments: list, cache_dir: str, voice_map: dict) -> AudioSegment:
    """
    Same as build_section_audio, but for manual post-production in an external
    editor (e.g. Audiomass): no 30s silence turns are inserted, and no
    ambience bed is overlaid. Just the spoken lines, back-to-back, with the
    normal short gap between turns. You add the 30s silences and room-tone
    ambience yourself afterward.
    """
    section_track = AudioSegment.silent(duration=0)

    for seg in segments:
        for turn in seg.turns:
            if turn.kind == "silence":
                # Stripped: no dead air inserted for "30 SECONDS OF SILENCE"
                # markers -- add these yourself in Audiomass.
                continue
            clip = tts_client.synthesize_line(
                text=turn.text, voice_id=_voice_for(turn, voice_map), tag=turn.tag, cache_dir=cache_dir
            )
            section_track += clip
            gap = config.GAP_AFTER_NARRATOR_MS if turn.kind == "narrator" else config.GAP_BETWEEN_TURNS_MS
            section_track += AudioSegment.silent(duration=gap)

    return section_track


def build_test_audio(
    test_id: str,
    sections: dict,
    cache_dir: str,
    output_path: str,
    dry: bool = False,
    voice_seed: int | None = None,
) -> str:
    """
    sections: {section_num: [Segment, ...]} as returned by parser.parse_test
    Renders Section 1..4 in order, crossfades them together, exports final mp3.

    dry=True skips 30s silence markers and the ambience bed entirely -- pure
    back-to-back speech, meant to be hand-edited afterward (e.g. in
    Audiomass) to add silences and ambience yourself.

    Every speaker (including the narrator) is assigned one random voice_id
    for the entire test -- see voice_assignment.py -- so nobody's voice
    changes partway through a section or between sections. Pass voice_seed
    for a reproducible assignment across repeated runs; leave it None for
    fresh randomization each time.
    """
    speakers = voice_assignment.collect_speakers(sections)
    voice_map = voice_assignment.assign_test_voices(speakers, seed=voice_seed)

    print(f"  Voice assignment for {test_id}:")
    for speaker, voice_id in sorted(voice_map.items()):
        print(f"    {speaker}: {voice_id}")

    builder = build_section_audio_dry if dry else build_section_audio

    full = AudioSegment.silent(duration=0)
    for sec_num in sorted(sections.keys()):
        segs = sections[sec_num]
        if not segs:
            continue
        sec_audio = builder(sec_num, segs, cache_dir, voice_map)
        if len(full) == 0:
            full = sec_audio
        elif dry:
            # No crossfade in dry mode either -- keep section boundaries
            # clean and obvious so they're easy to find and edit later.
            full += sec_audio
        else:
            full = full.append(sec_audio, crossfade=min(config.CROSSFADE_MS, len(sec_audio), len(full)))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    full.export(output_path, format="mp3", bitrate="192k")
    return output_path
