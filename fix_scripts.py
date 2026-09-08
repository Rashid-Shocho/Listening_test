"""
Normalizes raw script/sourceNotes text in data/tests.json so it matches the
format parser.py already handles correctly (Format A, as used by TEST01).

Fixes two bugs found in "TEST02-style" script text:

1. Multi-line silence markers ("30-SECOND SILENCE" + a following sentence
   that also contains "30 seconds ...") get matched TWICE by parser.py's
   SILENCE_RE, producing 60s of silence instead of 30s. This collapses any
   such block down to the single canonical marker line already used
   successfully in TEST01:

       30 SECONDS OF SILENCE (production marker — do not generate audio)

2. "[Neutral, clear IELTS narrator]" tag-only lines (used instead of an
   explicit "NARRATOR:" prefix) cause the parser to silently drop the
   narration entirely, since it has no current speaker to attach the text
   to. This rewrites those into "NARRATOR: <first line>" so parser.py's
   existing NARRATOR: handling picks up the whole block correctly.

Usage:
    python fix_scripts.py data/tests.json data/tests.fixed.json
"""
from __future__ import annotations

import json
import re
import sys

# --- Bug 1: collapse any multi-line "30-SECOND SILENCE" production-marker
# block (regardless of the exact wording used inside it) into one canonical
# single-line marker that only matches SILENCE_RE once.
SILENCE_BLOCK_RE = re.compile(
    r"30-SECOND SILENCE\n"
    r"\[PRODUCTION MARKER[^\]]*\]\n"
    r"(?:Insert exactly|Exactly) 30 seconds of TRUE DIGITAL SILENCE\.\n"
    r"No[^\n]*\n"
    r"(?:-[^\n]*\n?)*",
    re.IGNORECASE,
)
CANONICAL_SILENCE = "30 SECONDS OF SILENCE (production marker — do not generate audio)\n"

# --- Bug 2: "[Neutral, clear IELTS narrator]" tag-only line followed by the
# narration text on the next line(s) -> merge into "NARRATOR: <text>".
NARRATOR_TAG_RE = re.compile(r"\[Neutral, clear IELTS narrator\]\n")


def fix_text(text: str) -> tuple[str, int, int]:
    """Returns (fixed_text, silence_blocks_fixed, narrator_tags_fixed)."""
    silence_fixes = len(SILENCE_BLOCK_RE.findall(text))
    text = SILENCE_BLOCK_RE.sub(CANONICAL_SILENCE, text)

    narrator_fixes = len(NARRATOR_TAG_RE.findall(text))
    text = NARRATOR_TAG_RE.sub("NARRATOR: ", text)

    return text, silence_fixes, narrator_fixes


def fix_tests_json(data: dict) -> dict:
    total_silence, total_narrator = 0, 0
    for test_id, test in data.get("tests", {}).items():
        for sec_key, sec in test.get("sections", {}).items():
            if "script" in sec and sec["script"]:
                fixed, s, n = fix_text(sec["script"])
                sec["script"] = fixed
                total_silence += s
                total_narrator += n
        if "sourceNotes" in test and test["sourceNotes"]:
            fixed, s, n = fix_text(test["sourceNotes"])
            test["sourceNotes"] = fixed
            total_silence += s
            total_narrator += n
    print(f"Fixed {total_silence} double-counted silence blocks and "
          f"{total_narrator} dropped-narrator tag lines.")
    return data


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "data/tests.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "data/tests.fixed.json"
    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data = fix_tests_json(data)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")