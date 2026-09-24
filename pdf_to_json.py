"""
Converts the text extracted from "IELTS Listening — Audio Scripts by File Name"
(all 25 mock tests) into the tests.json format that main.py / parser.py expect.

Only the *_Voice.mp3 blocks are kept (Opening/Intro/Part1/Transition/Part2/
End/Full). Script QC notes, question papers, answer keys, ambience and map
prompts, audio-configuration notes and page numbers are all dropped.

Every spoken line is rewritten into one clean single-line form:
    NARRATOR: text
    Speaker: [tag] text
so the existing parser reads each turn correctly, whatever layout the PDF used
(inline "Name: [tag] text", or "Name:" / "[tag]" / "text" on separate lines,
or wrapped across PDF lines and page breaks).

Usage:
    python pdf_to_json.py lisining_pdf.txt data/tests.json
"""
from __future__ import annotations

import json
import re
import sys

TEST_HEAD_RE = re.compile(r"^MOCK TEST (\d+)\s+—\s+TEST(\d+)\s*$")
SECTION_HEAD_RE = re.compile(r"^SECTION (\d)\s*$")
# Full ("Test3_Sec1_Part1_Voice.mp3") or short ("Part1_Voice.mp3", Test 16) file names
FILE_RE = re.compile(r"^(?:Test\d+_Sec(\d)_)?([A-Za-z0-9]+)_(Voice|Ambient)\.mp3\s*$|^(?:Test\d+_Sec\d_)?Map\.png\s*$")
VOICE_KINDS = {"Opening", "Intro", "Part1", "Transition", "Part2", "End", "Full"}

SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z.'\-]*(?: [A-Z][A-Za-z.'\-]*){0,4}):\s*(.*)$")
TAG_LINE_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
NARRATOR_TAG_RE = re.compile(r"^\[Neutral, clear IELTS narrator\]\s*$", re.I)
PAGE_NUM_RE = re.compile(r"^\d{1,3}$")

# Labels that look like "Name:" but are production notes, not speakers.
NOT_SPEAKERS = {
    "Very subtle", "Mix", "Environment", "Use", "Include", "Stability", "Personality",
    "Delivery", "Avoid", "Required spatial arrangement", "Do NOT include", "Do not include",
    "Speaker", "Style", "Accent", "No", "Covers", "Design requirements", "Final answer",
    "Intentional correction", "Later duration", "Speaker guides students through",
    "Natural conversation including", "Research facts include",
}

SILENCE_RE = re.compile(r"30[ -]SECONDS? (OF )?(COMPLETE )?SILENCE|30-SECOND SILENCE", re.I)
# Lines belonging to a multi-line silence/production-marker block
SILENCE_NOISE_RE = re.compile(
    r"^(\[PRODUCTION MARKER.*|Insert exactly.*|Exactly 30 seconds.*|No:\s*|-\s*(speech|breathing|ambience|"
    r"music|room tone)\s*|\(production marker.*)$", re.I)

CANON_SILENCE = "30 SECONDS OF SILENCE (production marker — do not generate audio)"


def clean(s: str) -> str:
    s = s.replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def ends_sentence(s: str) -> bool:
    return bool(re.search(r"[.?!…\"”’)]\s*$", s.strip()))


def parse_voice_block(lines: list[str]) -> tuple[list[str], list[str]]:
    """Turn the raw lines of one *_Voice.mp3 block into clean script lines.
    Returns (script_lines, dropped_lines) -- dropped_lines is for auditing."""
    out: list[str] = []
    dropped: list[str] = []
    cur = None          # {"speaker":..., "tag":..., "text":...}
    wrap = False        # previous physical line was wrapped (trailing space)
    pending_tag = None
    speaker = None
    narrator_mode = False

    def flush():
        nonlocal cur
        if cur and cur["text"].strip():
            text = clean(cur["text"])
            if cur["speaker"] == "NARRATOR":
                out.append(f"NARRATOR: {text}")
            else:
                tag = f"[{clean(cur['tag'])}] " if cur["tag"] else ""
                out.append(f"{cur['speaker']}: {tag}{text}")
        cur = None

    i = 0
    stopped = False
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line or PAGE_NUM_RE.match(line):
            continue                      # page break: keep wrap state
        if stopped:
            dropped.append(line)
            continue

        # continuation of a wrapped line
        if wrap and cur is not None and not SPEAKER_RE.match(line) and not line.startswith("["):
            cur["text"] += " " + line
            wrap = raw.endswith(" ")
            continue
        wrap = False

        if SILENCE_RE.search(line):
            flush()
            out.append(CANON_SILENCE)
            narrator_mode = False
            continue
        if SILENCE_NOISE_RE.match(line):
            continue

        if NARRATOR_TAG_RE.match(line):
            flush()
            narrator_mode = True
            speaker = "NARRATOR"
            cur = {"speaker": "NARRATOR", "tag": None, "text": ""}
            continue

        if line.startswith("NARRATOR:"):
            flush()
            narrator_mode = True
            speaker = "NARRATOR"
            rest = line[len("NARRATOR:"):].strip()
            tm = TAG_LINE_RE.match(rest)
            if tm:
                rest = tm.group(2)
            cur = {"speaker": "NARRATOR", "tag": None, "text": rest}
            wrap = raw.endswith(" ")
            continue

        sm = SPEAKER_RE.match(line)
        if sm and sm.group(1) not in NOT_SPEAKERS and len(sm.group(1)) <= 40:
            flush()
            narrator_mode = False
            speaker = sm.group(1).strip()
            rest = sm.group(2).strip()
            pending_tag = None
            if rest:
                tm = TAG_LINE_RE.match(rest)
                if tm:
                    if tm.group(2).strip():
                        cur = {"speaker": speaker, "tag": tm.group(1), "text": tm.group(2)}
                    else:
                        pending_tag = tm.group(1)
                else:
                    cur = {"speaker": speaker, "tag": None, "text": rest}
            wrap = raw.endswith(" ") and cur is not None
            continue

        tm = TAG_LINE_RE.match(line)
        if tm and speaker and speaker != "NARRATOR":
            flush()
            if tm.group(2).strip():
                cur = {"speaker": speaker, "tag": tm.group(1), "text": tm.group(2)}
                wrap = raw.endswith(" ")
            else:
                pending_tag = tm.group(1)
            continue

        # plain text line
        if narrator_mode and cur is not None:
            # narrator text is often one sentence per physical line
            if looks_like_speech(line):
                cur["text"] += " " + line
                wrap = raw.endswith(" ")
                continue
        elif speaker and speaker != "NARRATOR":
            if cur is None and (pending_tag is not None or looks_like_speech(line)):
                cur = {"speaker": speaker, "tag": pending_tag, "text": line}
                pending_tag = None
                wrap = raw.endswith(" ")
                continue
            if cur is not None and looks_like_speech(line) and not ends_sentence(cur["text"]):
                cur["text"] += " " + line
                wrap = raw.endswith(" ")
                continue

        # anything else means the spoken part of this block is over
        flush()
        stopped = True
        dropped.append(line)

    flush()
    return out, dropped


STOP_WORDS_RE = re.compile(
    r"^(Script QC|QUESTIONS?\b|Questions?\s+\d|Complete the|Choose|Write (ONE|NO)|Answer|ANSWER|"
    r"Test\s*\d+\s+—|TEST\s*\d+\s+—|Audio Configuration|AUDIO CONFIGURATION|SPEAKER$|Label |"
    r"Q\d+|Match|Which |Environment|Mix|Very subtle|Create |Final |✓)")


def looks_like_speech(line: str) -> bool:
    if STOP_WORDS_RE.match(line):
        return False
    if line.isupper() and len(line) > 3:
        return False
    return bool(re.match(r"^[A-Z0-9\"'“‘(…a-z]", line))


def split_tests(lines: list[str]) -> dict[str, list[str]]:
    tests, cur_id = {}, None
    for l in lines:
        m = TEST_HEAD_RE.match(l.strip())
        if m:
            cur_id = f"TEST{int(m.group(2)):02d}"
            tests[cur_id] = []
            continue
        if cur_id:
            tests[cur_id].append(l)
    return tests


def extract_test(test_id: str, lines: list[str]) -> tuple[dict, dict]:
    """Returns ({section_num: script_text}, audit)."""
    num = int(test_id[4:])
    blocks: list[tuple[int, str, list[str]]] = []   # (section, kind, raw lines)
    section = 1
    cur_block = None
    seen_kinds: dict[int, set] = {}
    for l in lines:
        s = l.strip()
        hm = SECTION_HEAD_RE.match(s)
        if hm:
            n = int(hm.group(1))
            # only move forward -- trailing "assembly structure" pages repeat SECTION 1
            if n >= section:
                section = n
            cur_block = None
            continue
        fm = FILE_RE.match(s)
        if fm:
            sec = int(fm.group(1)) if fm.group(1) else section
            kind = fm.group(2)
            if fm.group(3) == "Voice" and kind in VOICE_KINDS and kind not in seen_kinds.setdefault(sec, set()):
                seen_kinds[sec].add(kind)
                cur_block = (sec, kind, [])
                blocks.append(cur_block)
            else:
                cur_block = None
            continue
        if cur_block is not None:
            cur_block[2].append(l)

    sections: dict[int, list[str]] = {}
    audit = {"dropped": [], "empty_blocks": []}
    for sec, kind, raw in blocks:
        script, dropped = parse_voice_block(raw)
        fname = f"Test{num}_Sec{sec}_{kind}_Voice.mp3"
        if not any(not x.startswith("30 SECONDS") for x in script):
            audit["empty_blocks"].append(fname)
            continue
        sections.setdefault(sec, []).append(fname)
        sections[sec].extend(script)
        if dropped:
            audit["dropped"].append((fname, dropped[:3]))
    return {k: "\n".join(v) + "\n" for k, v in sorted(sections.items())}, audit


def extract_answer_key(lines: list[str]) -> dict:
    """Best-effort: reads 'N answer' lines that follow an ANSWERS / Answer Key
    heading. Only returned when all 40 answers were found."""
    key, active = {}, False
    for l in lines:
        s = l.strip()
        if re.match(r"^(ANSWERS?|Answers?|.*ANSWER KEY|.*Answer Key)\s*$", s):
            active = True
            continue
        if not active or not s or PAGE_NUM_RE.match(s):
            continue
        m = re.match(r"^(\d{1,2})[.)]?\s+(\S.{0,60}?)\s*$", s)
        if m and 1 <= int(m.group(1)) <= 40:
            key.setdefault(f"{int(m.group(1)):02d}", m.group(2))
        else:
            active = False
    return dict(sorted(key.items())) if len(key) == 40 else {}


# ---------------------------------------------------------------------------
# Cast (accent + gender per speaker, per test). Section 2 comes straight from
# the PDF's "AUDIO CONFIGURATION" block; everyone else is set here so every
# test gets a realistic IELTS mix of accents. Edit freely.
# ---------------------------------------------------------------------------
FEMALE = {"Emily", "Sofia", "Nina", "Maya", "Laura", "Priya", "Rachel", "Emma", "Helen", "Leah",
          "Sophie", "Nora", "Sarah", "Anna", "Mia", "Claire", "Lily", "Olivia", "Natalie",
          "Dr. Harris", "Dr. Patel", "Dr. Morgan", "Dr. Campbell", "Dr. Taylor"}
MALE = {"Daniel", "Liam", "Mark", "Alex", "Owen", "Ethan", "Thomas", "Noah", "Marcus", "Adam",
        "Lucas", "James", "Oliver", "Ben", "Michael", "Ryan", "David", "Tom", "Nathan",
        "Dr. Wilson", "Dr. Carter", "Dr. Lewis", "Dr. Evans", "Professor Bennett"}
ROTATE = ["Canadian", "American", "Australian", "British"]
SEC2_CONFIG_RE = re.compile(r"(Female|Male)\s*[—·-]\s*(Australian|American|Canadian|British)", re.I)


def section2_config(lines: list[str]) -> tuple[str, str] | None:
    for i, l in enumerate(lines):
        if l.strip().upper() in ("AUDIO CONFIGURATION",):
            blob = " ".join(x.strip() for x in lines[i + 1:i + 8])
            m = SEC2_CONFIG_RE.search(blob)
            if m:
                return m.group(2).capitalize(), m.group(1).lower()
            m = re.search(r"Accent:\s*(\w+)", blob)
            if m:
                return m.group(1).capitalize(), "female"
    return None


def build_cast(test_id: str, sections: dict[int, str], tlines: list[str]) -> dict:
    n = int(test_id[4:])
    cast = {"NARRATOR": {"accent": "British", "gender": "female", "role": "Narrator"}}
    order = {sec: [s for s in ordered_speakers(txt) if s != "NARRATOR"] for sec, txt in sections.items()}

    def gender(name, default="female"):
        name = name.replace("Student ", "")
        return "female" if name in FEMALE else "male" if name in MALE else default

    def put(name, accent, g, role):
        cast.setdefault(name, {"accent": accent, "gender": g, "role": role})

    for i, name in enumerate(order.get(1, [])):
        # staff member British; the caller's accent rotates across tests
        put(name, "British" if i == 0 else ROTATE[n % 3], gender(name), "Section 1")
    cfg = section2_config(tlines) or ("Australian", "female")
    for name in order.get(2, []):
        put(name, cfg[0], cfg[1], "Section 2 guide")
    for i, name in enumerate(order.get(3, [])):
        accent = "British" if i != 1 else ROTATE[(n + 1) % 3]
        put(name, accent, gender(name), "Section 3 supervisor" if i == 0 else "Section 3 student")
    for name in order.get(4, []):
        put(name, ["British", "American", "Canadian", "British"][n % 4],
            "male" if n % 2 else "female", "Section 4 lecturer")
    return cast


def ordered_speakers(script: str) -> list[str]:
    seen = []
    for m in re.finditer(r"^([^:\n]+):", script, re.M):
        s = m.group(1)
        if not s.startswith(("Test", "30 SECONDS")) and s not in seen:
            seen.append(s)
    return seen


def relabel_repeated_names(sections: dict[int, str]) -> dict[int, str]:
    """If the same first name is two different people in two sections of one
    test (e.g. TEST08: Nora the receptionist and Nora the student), relabel the
    later one "Student Nora" so each character keeps a separate voice. Only the
    label changes -- the spoken text is untouched."""
    first_seen: dict[str, int] = {}
    for sec in sorted(sections):
        for s in ordered_speakers(sections[sec]):
            if s == "NARRATOR":
                continue
            if s in first_seen and first_seen[s] != sec:
                sections[sec] = re.sub(rf"^{re.escape(s)}:", f"Student {s}:", sections[sec], flags=re.M)
            else:
                first_seen.setdefault(s, sec)
    return sections


def speakers_in(script: str) -> set:
    return {m.group(1) for m in re.finditer(r"^([^:\n]+):", script, re.M)
            if not m.group(1).startswith("Test") and not m.group(1).startswith("30 SECONDS")}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "lisining_pdf.txt"
    dst = sys.argv[2] if len(sys.argv) > 2 else "data/tests.json"
    lines = open(src, encoding="utf-8").read().split("\n")
    out = {"schemaVersion": "1.0", "sourceFile": "IELTS Listening — Audio Scripts by File Name (25 mock tests)",
           "tests": {}}
    report = []
    for test_id, tl in split_tests(lines).items():
        sections, audit = extract_test(test_id, tl)
        sections = relabel_repeated_names(sections)
        tobj = {"testId": test_id, "title": f"MOCK TEST {int(test_id[4:])}",
                "speakers": build_cast(test_id, sections, tl), "sections": {}}
        for n in (1, 2, 3, 4):
            if n in sections:
                tobj["sections"][f"section{n}"] = {"sectionNumber": n, "script": sections[n]}
        missing = [n for n in (1, 2, 3, 4) if n not in sections]
        if missing:
            tobj["notes"] = (f"Source PDF has no spoken script for section(s) {missing} of this test "
                             f"(outline only), so only section(s) {sorted(sections)} are generated.")
        ak = extract_answer_key(tl)
        if ak:
            tobj["answerKey"] = ak
        out["tests"][test_id] = tobj
        report.append((test_id, sections, audit))

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    for test_id, sections, audit in report:
        parts = []
        for n in (1, 2, 3, 4):
            s = sections.get(n, "")
            turns = sum(1 for l in s.split("\n") if ":" in l and not l.startswith("Test"))
            parts.append(f"S{n}:{turns}")
        print(test_id, " ".join(parts), "| speakers:", sorted(set().union(*[speakers_in(s) for s in sections.values()]) - {"NARRATOR"}))
        if audit["empty_blocks"]:
            print("   no script text:", ", ".join(audit["empty_blocks"]))
    print(f"\nWrote {dst}")


if __name__ == "__main__":
    main()
