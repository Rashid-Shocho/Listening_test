"""
Free diagnostic -- makes ZERO ElevenLabs API calls. Confirms exactly what
speakers/turns each section of a given test will actually contain, so you
can verify the fix (or find the real cause) before spending any credits.

Usage:
    python diagnose.py data/tests.json TEST04
"""
import json
import sys

from parser import parse_test


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/tests.json"
    test_id = sys.argv[2] if len(sys.argv) > 2 else "TEST04"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_obj = data["tests"].get(test_id)
    if not test_obj:
        print(f"'{test_id}' not found in {path}. Available: {list(data['tests'].keys())}")
        return

    has_source_notes = bool(test_obj.get("sourceNotes", "").strip())
    print(f"sourceNotes present for {test_id}: {has_source_notes}")
    print(f"(If False, the split_source_notes_by_section bug can't be the cause here --")
    print(f" the per-section 'script' fallback is used directly, which is inherently isolated.)")
    print()

    sections = parse_test(test_obj)
    for sec_num, segs in sorted(sections.items()):
        speakers = set()
        n_turns = 0
        for seg in segs:
            for t in seg.turns:
                n_turns += 1
                if t.kind in ("speech", "narrator"):
                    speakers.add(t.speaker)
        print(f"Section {sec_num}: {n_turns} turns, speakers = {sorted(speakers)}")


if __name__ == "__main__":
    main()