"""
Assembles parsed script Segments into final per-test MP3 files:

  turns -> per-line TTS clips -> section track (with gaps + true silence)
        -> ambience overlay (skipped under the 30s silence)
        -> section files concatenated (with short crossfade) -> Test_N.mp3
"""

from __future__ import annotations

import os
import random

from pydub import AudioSegment
from pydub.generators import WhiteNoise

import config
import tts_client
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


def build_segment_track(segment: Segment, cache_dir: str) -> AudioSegment:
    """Concatenate all turns in one Segment (one original 'file') into audio."""
    track = AudioSegment.silent(duration=0)
    for turn in segment.turns:
        if turn.kind == "silence":
            track += AudioSegment.silent(duration=turn.ms or config.SILENCE_MARKER_MS)
            continue

        clip = tts_client.synthesize_line(
            text=turn.text, speaker=turn.speaker or "narrator", tag=turn.tag, cache_dir=cache_dir
        )
        track += clip
        gap = config.GAP_AFTER_NARRATOR_MS if turn.kind == "narrator" else config.GAP_BETWEEN_TURNS_MS
        track += AudioSegment.silent(duration=gap)
    return track


def build_section_audio(section_num: int, segments: list, cache_dir: str) -> AudioSegment:
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
                text=turn.text, speaker=turn.speaker or "narrator", tag=turn.tag, cache_dir=cache_dir
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


def build_test_audio(test_id: str, sections: dict, cache_dir: str, output_path: str) -> str:
    """
    sections: {section_num: [Segment, ...]} as returned by parser.parse_test
    Renders Section 1..4 in order, crossfades them together, exports final mp3.
    """
    full = AudioSegment.silent(duration=0)
    for sec_num in sorted(sections.keys()):
        segs = sections[sec_num]
        if not segs:
            continue
        sec_audio = build_section_audio(sec_num, segs, cache_dir)
        if len(full) == 0:
            full = sec_audio
        else:
            full = full.append(sec_audio, crossfade=min(config.CROSSFADE_MS, len(sec_audio), len(full)))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    full.export(output_path, format="mp3", bitrate="192k")
    return output_path