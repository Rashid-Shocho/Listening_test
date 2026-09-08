"""
IELTS Listening audio generation pipeline.

Usage:
    python3 main.py --input data/tests.json --tests TEST01 TEST02
    python3 main.py --input data/tests.json --all

Architecture (matches the intended production pipeline):

    JSON test scripts
        -> parser.parse_test()            (structured turns per section)
        -> tts_client.synthesize_line()    (ElevenLabs API, one voice/speaker)
        -> audio_pipeline.build_test_audio()
             - 30s TRUE SILENCE at transition markers
             - subtle ambience/room-tone bed under speech
             - Section 1-4 merged with short crossfades
        -> output/<TestID>.mp3

Set ELEVENLABS_API_KEY in the environment to synthesize real speech.
Without it, the pipeline runs in MOCK mode (silent placeholder clips of
correct duration) so the full assembly can be validated end-to-end.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import config
from parser import parse_test
from audio_pipeline import build_test_audio


def load_data(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run(input_path: str, test_ids: list[str] | None, output_dir: str, cache_dir: str, dry: bool = False,
        voice_seed: int | None = None) -> list[str]:
    data = load_data(input_path)
    all_tests = data.get("tests", {})

    if test_ids:
        missing = [t for t in test_ids if t not in all_tests]
        if missing:
            print(f"WARNING: test id(s) not found in input: {missing}", file=sys.stderr)
        selected = {k: v for k, v in all_tests.items() if k in test_ids}
    else:
        selected = all_tests

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    produced = []
    mode = "MOCK (no ELEVENLABS_API_KEY set)" if config.MOCK_MODE else f"LIVE ({config.ELEVENLABS_MODEL_ID})"
    print(f"Pipeline mode: {mode}")

    for test_id, test_obj in selected.items():
        print(f"\n=== Building {test_id}: {test_obj.get('title', '')} ===")
        sections = parse_test(test_obj)
        for sec_num, segs in sorted(sections.items()):
            n_turns = sum(len(s.turns) for s in segs)
            print(f"  Section {sec_num}: {len(segs)} audio segments, {n_turns} turns")

        out_path = os.path.join(output_dir, f"{test_id}.mp3")
        try:
            build_test_audio(test_id, sections, cache_dir, out_path, dry=dry, voice_seed=voice_seed)
        except Exception as e:
            print(f"  !! FAILED to build {test_id}: {e}", file=sys.stderr)
            print(f"  Re-run the same command later -- already-synthesized lines are cached, "
                  f"so it will resume quickly instead of starting over.", file=sys.stderr)
            continue
        size_kb = os.path.getsize(out_path) / 1024
        print(f"  -> {out_path} ({size_kb:.0f} KB)")
        produced.append(out_path)

    return produced


def main():
    ap = argparse.ArgumentParser(description="IELTS Listening audio generator")
    ap.add_argument("--input", default="data/tests.json", help="Path to the tests JSON file")
    ap.add_argument("--tests", nargs="*", help="Specific test IDs to build, e.g. TEST01 TEST02")
    ap.add_argument("--all", action="store_true", help="Build every test found in the input file")
    ap.add_argument("--output-dir", default=config.OUTPUT_DIR)
    ap.add_argument("--cache-dir", default=config.CACHE_DIR)
    ap.add_argument("--dry", action="store_true",
                     help="Skip 30s silence markers and ambience overlay -- pure back-to-back "
                          "speech, meant for you to hand-edit afterward (e.g. in Audiomass).")
    ap.add_argument("--voice-seed", type=int, default=None,
                     help="Seed the random voice assignment for a reproducible cast across "
                          "repeated runs. Omit for a fresh random cast each run.")
    args = ap.parse_args()

    if not args.tests and not args.all:
        ap.error("Specify --tests TEST01 TEST02 ... or --all")

    produced = run(args.input, args.tests, args.output_dir, args.cache_dir, dry=args.dry, voice_seed=args.voice_seed)
    print("\nDone. Produced:")
    for p in produced:
        print(" ", p)


if __name__ == "__main__":
    main()
    