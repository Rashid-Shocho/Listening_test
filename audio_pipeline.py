"""
Assembles parsed script Segments into final per-test MP3 files:

  turns -> per-line TTS clips -> section track (clean speech, normal
        turn gaps only -- no ambience, no 30s silence) -> section files
        concatenated -> Test_N.mp3

Every synthesize_line call is given a voice_id resolved from a per-test
voice_map (speaker -> voice_id), built once by voice_assignment.py at the
start of build_test_audio() so each speaker's voice is randomized but
stays fixed for the whole test -- see voice_assignment.py.
"""

from __future__ import annotations

import os

from pydub import AudioSegment

import config
import tts_client
import voice_assignment
from parser import Segment


def _voice_for(turn, voice_map: dict) -> str:
    key = turn.speaker or "NARRATOR"
    if key in voice_map:
        return voice_map[key]
    # Shouldn't happen (voice_map is built from the same turns beforehand),
    # but if a speaker string is somehow missing, resolve it deterministically
    # from the key itself rather than calling assign_test_voices() fresh --
    # that used no seed and would hand back a brand-new random voice every
    # single time it fired, which is exactly how a 2-person scene could
    # suddenly pick up an extra, inconsistent voice mid-test. A per-key
    # seed means the same missing speaker always resolves to the same
    # voice, even across repeated fallback hits.
    fallback = voice_assignment.assign_test_voices([key], seed=hash(key) & 0xFFFFFFFF)
    return fallback[key]


def build_segment_track(segment: Segment, cache_dir: str, voice_map: dict) -> AudioSegment:
    """
    Concatenate all turns in one Segment (one original 'file') into audio.
    "30 SECONDS OF SILENCE" markers are skipped entirely -- no dead air is
    inserted anywhere in the generated audio.
    """
    track = AudioSegment.silent(duration=0)
    for turn in segment.turns:
        if turn.kind == "silence":
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
    Build one full IELTS section (Intro -> Part1 -> Transition -> Part2 ->
    End). Pure clean speech: no ambience bed of any kind, and "30 SECONDS
    OF SILENCE" markers are skipped entirely -- just the spoken lines with
    the normal short gap between turns.
    """
    section_track = AudioSegment.silent(duration=0)

    for seg in segments:
        seg_audio = AudioSegment.silent(duration=0)
        for turn in seg.turns:
            if turn.kind == "silence":
                continue
            clip = tts_client.synthesize_line(
                text=turn.text, voice_id=_voice_for(turn, voice_map), tag=turn.tag, cache_dir=cache_dir
            )
            seg_audio += clip
            gap = config.GAP_AFTER_NARRATOR_MS if turn.kind == "narrator" else config.GAP_BETWEEN_TURNS_MS
            seg_audio += AudioSegment.silent(duration=gap)

        section_track += seg_audio

    return section_track


def build_test_audio(
    test_id: str,
    sections: dict,
    cache_dir: str,
    output_path: str,
    voice_seed: int | None = None,
) -> str:
    """
    sections: {section_num: [Segment, ...]} as returned by parser.parse_test
    Renders Section 1..4 in order and concatenates them (no crossfade --
    section boundaries stay clean and obvious) into the final mp3.

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

    full = AudioSegment.silent(duration=0)
    for sec_num in sorted(sections.keys()):
        segs = sections[sec_num]
        if not segs:
            continue
        sec_audio = build_section_audio(sec_num, segs, cache_dir, voice_map)
        full += sec_audio

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    full.export(output_path, format="mp3", bitrate="192k")
    return output_path