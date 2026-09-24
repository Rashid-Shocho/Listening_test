"""
Assembles parsed script Segments into final per-test MP3 files:

  turns -> grouped per speaker -> TTS clips -> section tracks -> Test.mp3

Consecutive lines by the same speaker are merged into one ElevenLabs request
(up to config.MAX_CHARS_PER_REQUEST characters). Sending each short line on
its own made v3 re-interpret the voice every time, which is what caused
characters to drift, sound like a different person, or slip into a whisper.
"""

from __future__ import annotations

import os

from pydub import AudioSegment

import config
import tts_client
import voice_assignment
from parser import Segment


def _voice_for(speaker: str | None, voice_map: dict) -> str:
    key = speaker or "NARRATOR"
    if key in voice_map:
        return voice_map[key]
    fallback = voice_assignment.assign_test_voices([key], seed=sum(map(ord, key)))
    return fallback[key]


def _group_turns(turns: list) -> list[dict]:
    groups: list[dict] = []
    for t in turns:
        if t.kind == "silence" or not t.text:
            continue       # "30 SECONDS OF SILENCE" markers produce no audio
        piece = tts_client._tagged_text(t.text, t.tag)
        g = groups[-1] if groups else None
        if (g and g["speaker"] == t.speaker and g["kind"] == t.kind
                and len(g["text"]) + len(piece) + 1 <= config.MAX_CHARS_PER_REQUEST):
            g["text"] += " " + piece
        else:
            groups.append({"speaker": t.speaker, "kind": t.kind, "text": piece})
    return groups


def build_section_audio(section_num: int, segments: list, cache_dir: str, voice_map: dict) -> AudioSegment:
    """One full IELTS section: clean speech with normal gaps between turns."""
    track = AudioSegment.silent(duration=0)
    for seg in segments:
        for g in _group_turns(seg.turns):
            clip = tts_client.synthesize_line(
                text=g["text"], voice_id=_voice_for(g["speaker"], voice_map), tag=None, cache_dir=cache_dir
            )
            track += clip
            gap = config.GAP_AFTER_NARRATOR_MS if g["kind"] == "narrator" else config.GAP_BETWEEN_TURNS_MS
            track += AudioSegment.silent(duration=gap)
    return track


def count_requests(sections: dict) -> int:
    return sum(len(_group_turns(seg.turns)) for segs in sections.values() for seg in segs)


def build_test_audio(
    test_id: str,
    sections: dict,
    cache_dir: str,
    output_path: str,
    voice_seed: int | None = None,
    profiles: dict | None = None,
) -> str:
    """
    sections: {section_num: [Segment, ...]} from parser.parse_test.
    profiles: the test's "speakers" block from the JSON (accent/gender per speaker).
    """
    speakers = voice_assignment.collect_speakers(sections)
    voice_map = voice_assignment.assign_test_voices(speakers, seed=voice_seed, profiles=profiles)

    print(f"  Voice assignment for {test_id}:")
    for speaker, voice_id in sorted(voice_map.items()):
        p = voice_assignment._profile_for(speaker, profiles)
        print(f"    {speaker:<36} {p['gender']:<6} {p['accent']:<10} {voice_id}")
    print(f"  ElevenLabs requests needed: {count_requests(sections)} (cached ones are free)")

    full = AudioSegment.silent(duration=0)
    for sec_num in sorted(sections.keys()):
        segs = sections[sec_num]
        if not segs:
            continue
        full += build_section_audio(sec_num, segs, cache_dir, voice_map)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    full.export(output_path, format="mp3", bitrate="192k")
    return output_path
