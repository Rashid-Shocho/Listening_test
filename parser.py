"""
Parses the raw script text stored in the source JSON (per test -> sourceNotes,
or per-section "script" field) into a structured list of audio *segments*.

Each segment corresponds to one "file" in the original manifest
(e.g. Test1_Sec1_Intro_Voice.mp3, Test1_Sec1_Part1_Voice.mp3, ...) and
contains an ordered list of *turns*:

    Turn(kind="narrator", speaker="NARRATOR", tag=None, text="...")
    Turn(kind="speech",   speaker="Emily",    tag="warm", text="...")
    Turn(kind="silence",  speaker=None,       tag=None, text=None, ms=30000)

This is intentionally tolerant of the two slightly different script
formats seen in the sample data:

  Format A (Test 1 style):   "Emily: [warm] Good morning ..."
  Format B (Test 2 style):   "Alex:\n[confident]\nWe've narrowed down ..."
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


FILENAME_RE = re.compile(r"^(Test\d+_Sec\d+_[A-Za-z0-9]+_(?:Voice|Ambient|Map|VisualOptions))\.(?:mp3|png)\s*$")
SILENCE_RE = re.compile(r"30[ -]SECOND|30 SECONDS OF SILENCE", re.IGNORECASE)
SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z .'\-]{1,40}?):\s*(.*)$")
TAG_INLINE_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
TAG_ONLY_RE = re.compile(r"^\[([^\]]+)\]$")

# Lines that are pure production/QC noise we should skip entirely.
SKIP_LINE_PATTERNS = [
    re.compile(r"^Script QC$", re.I),
    re.compile(r"^Answer-bearing", re.I),
    re.compile(r"^No filler", re.I),
    re.compile(r"^No answer-bearing", re.I),
    re.compile(r"^No consecutive", re.I),
    re.compile(r"^No excessive", re.I),
    re.compile(r"^No artificial", re.I),
    re.compile(r"^No invented", re.I),
    re.compile(r"^No simultaneous", re.I),
    re.compile(r"^Short acknowledgements", re.I),
    re.compile(r"^Closing line", re.I),
    re.compile(r"^The \"two weeks", re.I),
    re.compile(r"^Intentional correction", re.I),
    re.compile(r"^Final answer", re.I),
    re.compile(r"^Later duration", re.I),
    re.compile(r"^These corrections", re.I),
    re.compile(r"^All answer-bearing", re.I),
    re.compile(r"^\[PRODUCTION MARKER", re.I),
    re.compile(r"^No:\s*$", re.I),
    re.compile(r"^-\s*(speech|breathing|ambience|music|room tone)\s*$", re.I),
    re.compile(r"^\d+$"),  # bare page numbers
]

# Once we hit any of these, everything to end-of-block is metadata / questions
# / answer keys / audio-configuration notes -> not spoken dialogue.
STOP_SECTION_RE = re.compile(
    r"^(Questions?\s+\d|QUESTIONS\s+\d|Complete the notes|Choose the correct|"
    r"ANSWERS?$|ANSWERS?\b|Who will be responsible|Test\d+_Sec\d+_(Ambient|Map|VisualOptions)|"
    r"Audio Configuration|AUDIO CONFIGURATION|RIVERSIDE|LAKESIDE|Environment:|Quiet |"
    r"Speaker:$|Personality:|Delivery:|Stability:|Use:$|Avoid:$|Accent:|Create |Include:|"
    r"Required spatial|MAIN ENTRANCE|Test \d+ — |TEST \d+ —)",
)


@dataclass
class Turn:
    kind: str                       # "narrator" | "speech" | "silence"
    speaker: Optional[str] = None
    tag: Optional[str] = None
    text: Optional[str] = None
    ms: Optional[int] = None


@dataclass
class Segment:
    name: str                       # e.g. Test1_Sec1_Part1_Voice
    turns: list = field(default_factory=list)


def _is_skip_line(line: str) -> bool:
    return any(p.match(line) for p in SKIP_LINE_PATTERNS)


def _clean_narrator_text(lines, idx):
    """Collect the narrator sentence(s) that follow a NARRATOR: marker."""
    text_parts = []
    first = lines[idx]
    m = re.match(r"^NARRATOR:\s*(.*)$", first)
    if m and m.group(1):
        text_parts.append(m.group(1))
    j = idx + 1
    while j < len(lines):
        nxt = lines[j].strip()
        if not nxt:
            break
        if (FILENAME_RE.match(nxt) or SPEAKER_RE.match(nxt) or SILENCE_RE.search(nxt)
                or STOP_SECTION_RE.match(nxt)):
            break
        text_parts.append(nxt)
        j += 1
    return " ".join(text_parts).strip(), j


def parse_section_script(raw_text: str, section_prefix_hint: str = "") -> list:
    """
    Parse one section's `script` (or a slice of sourceNotes) into a list of
    Segment objects, stopping once we reach the printed Questions/Answers/
    Ambient/Map/AudioConfiguration boilerplate for that section.
    """
    lines = [l.rstrip() for l in raw_text.split("\n")]
    segments: list = []
    current: Optional[Segment] = None
    current_speaker: Optional[str] = None
    pending_tag: Optional[str] = None

    i = 0
    n = len(lines)
    stopped = False
    in_qc_block = False

    while i < n and not stopped:
        raw_line = lines[i]
        line = raw_line.strip()

        if not line:
            i += 1
            continue

        # "Script QC" blocks are production notes, not dialogue -- skip
        # every line until the next file marker or silence marker.
        if re.match(r"^Script QC$", line, re.I):
            in_qc_block = True
            i += 1
            continue
        if in_qc_block:
            if FILENAME_RE.match(line) or SILENCE_RE.search(line):
                in_qc_block = False
                # fall through to normal handling below
            else:
                i += 1
                continue

        # New file/segment boundary, e.g. "Test1_Sec1_Part1_Voice.mp3"
        fm = FILENAME_RE.match(line)
        if fm:
            fname = fm.group(1)
            if fname.endswith("_Ambient") or fname.endswith("_Map") or fname.endswith("_VisualOptions"):
                # Everything spoken for this section is done.
                stopped = True
                break
            current = Segment(name=fname)
            segments.append(current)
            current_speaker = None
            pending_tag = None
            i += 1
            continue

        # 30-second silence marker
        if SILENCE_RE.search(line):
            if current is None:
                current = Segment(name=f"{section_prefix_hint}_Transition")
                segments.append(current)
            current.turns.append(Turn(kind="silence", ms=30_000))
            i += 1
            continue

        # Stop once we hit the printed Q&A / metadata block for this section
        if STOP_SECTION_RE.match(line):
            stopped = True
            break

        if _is_skip_line(line):
            i += 1
            continue

        # Narrator line
        if line.startswith("NARRATOR:"):
            text, nxt_i = _clean_narrator_text(lines, i)
            if current is None:
                current = Segment(name=f"{section_prefix_hint}_Narration")
                segments.append(current)
            if text:
                current.turns.append(Turn(kind="narrator", speaker="NARRATOR", text=text))
            i = nxt_i
            continue

        # "Speaker:" possibly alone on its own line (Format B), or with
        # "[tag] rest of line" on the same line (Format A).
        sm = SPEAKER_RE.match(line)
        if sm:
            speaker, rest = sm.group(1).strip(), sm.group(2).strip()
            current_speaker = speaker
            pending_tag = None
            if current is None:
                current = Segment(name=f"{section_prefix_hint}_Dialogue")
                segments.append(current)

            if rest:
                tm = TAG_INLINE_RE.match(rest)
                if tm:
                    tag, text = tm.group(1), tm.group(2).strip()
                    if text:
                        current.turns.append(Turn(kind="speech", speaker=speaker, tag=tag, text=text))
                    else:
                        pending_tag = tag
                else:
                    current.turns.append(Turn(kind="speech", speaker=speaker, tag=None, text=rest))
            i += 1
            continue

        # A bare "[tag]" line (Format B) — remember it, apply to next text line
        tom = TAG_ONLY_RE.match(line)
        if tom:
            pending_tag = tom.group(1)
            i += 1
            continue

        # A "[tag] text" line without a leading "Speaker:" (continuation, Format B)
        tim = TAG_INLINE_RE.match(line)
        if tim and current_speaker:
            tag, text = tim.group(1), tim.group(2).strip()
            if current is None:
                current = Segment(name=f"{section_prefix_hint}_Dialogue")
                segments.append(current)
            if text:
                current.turns.append(Turn(kind="speech", speaker=current_speaker, tag=tag, text=text))
            else:
                pending_tag = tag
            i += 1
            continue

        # Plain continuation line: text for current_speaker (with any pending tag)
        if current_speaker and current is not None:
            current.turns.append(Turn(kind="speech", speaker=current_speaker, tag=pending_tag, text=line))
            pending_tag = None
            i += 1
            continue

        # Anything else (stray heading/number) -> ignore
        i += 1

    # Drop empty trailing segments
    segments = [s for s in segments if s.turns]

    # Merge consecutive speech turns from the same speaker (source-line-wrap
    # artifacts, e.g. a sentence split across two physical lines) into one
    # turn, so each turn = one continuous utterance for TTS.
    for seg in segments:
        merged: list = []
        for t in seg.turns:
            if (merged and t.kind == "speech" and merged[-1].kind == "speech"
                    and merged[-1].speaker == t.speaker and t.tag is None):
                merged[-1].text = f"{merged[-1].text} {t.text}".strip()
            else:
                merged.append(t)
        seg.turns = merged

    return segments


def split_source_notes_by_section(test_id: str, source_notes: str) -> dict:
    """
    sourceNotes holds the *whole* test's script concatenated. Some per-section
    "script" fields in the source JSON are truncated or corrupted (seen in
    the sample data for TEST02/section1), so sourceNotes is the more
    reliable source of truth. We slice it into 4 chunks using the first
    occurrence of each section's "_Sec{n}_Intro_Voice" (or, for section 1,
    the very start of the text) as boundaries.
    """
    bounds = {}
    for sec_num in (1, 2, 3, 4):
        pat = re.compile(rf"{re.escape(test_id)}_Sec{sec_num}_\w*Intro_Voice")
        m = pat.search(source_notes)
        if m:
            bounds[sec_num] = m.start()
    if 1 not in bounds:
        bounds[1] = 0

    ordered = sorted(bounds.items())
    chunks = {}
    for idx, (sec_num, start) in enumerate(ordered):
        end = ordered[idx + 1][1] if idx + 1 < len(ordered) else len(source_notes)
        chunks[sec_num] = source_notes[start:end]
    return chunks


def parse_test(test_obj: dict) -> dict:
    """
    Given one test's dict, return {section_number: [Segment, ...]}.

    Prefers sourceNotes (full, more reliable script text) when available and
    it actually contains recognizable dialogue for a section; falls back to
    the per-section "script" field otherwise.
    """
    out = {}
    test_id = test_obj.get("testId", "TEST")
    sections = test_obj.get("sections", {})
    source_notes = test_obj.get("sourceNotes", "") or ""

    chunks = split_source_notes_by_section(test_id, source_notes) if source_notes else {}

    for key, sec in sections.items():
        sec_num = sec.get("sectionNumber")
        prefix = f"{test_id}_Sec{sec_num}"

        segs = []
        if sec_num in chunks:
            segs = parse_section_script(chunks[sec_num], section_prefix_hint=prefix)

        # Fall back to the per-section "script" field if sourceNotes gave us
        # nothing usable (no speech/narrator turns) for this section.
        has_speech = any(t.kind in ("speech", "narrator") for s in segs for t in s.turns)
        if not has_speech:
            script = sec.get("script", "")
            segs = parse_section_script(script, section_prefix_hint=prefix)

        out[sec_num] = segs
    return out