"""
Randomized-but-consistent voice assignment.

Each speaker in a test gets exactly one voice_id for the whole test, drawn
from config.ACCENT_GENDER_POOLS using that speaker's accent/gender. The
accent/gender comes from the test's own "speakers" block in the JSON (so the
same label, e.g. "Arts Centre Guide", can be female in one test and male in
another), falling back to config.SPEAKER_PROFILES.

The narrator is the exception: it always gets config.NARRATOR_VOICE_ID, the
same voice in every test.

Pass `seed` (main.py --voice-seed) to get the same cast on every run, which
also lets the cache be reused instead of paying for the lines again.
"""

from __future__ import annotations

import random

import config


def _profile_for(speaker: str, profiles: dict | None = None) -> dict:
    for table in (profiles or {}, config.SPEAKER_PROFILES):
        if speaker in table:
            return table[speaker]
        lower = speaker.lower()
        for name, profile in table.items():
            if name.lower() == lower:
                return profile
    return config.DEFAULT_PROFILE


def _pick_voice_id(accent: str, gender: str, used: set, rng: random.Random) -> str:
    pool = config.ACCENT_GENDER_POOLS.get(accent, {}).get(gender, [])
    if not pool:
        pool = config.ACCENT_GENDER_POOLS.get("British", {}).get(gender, [])
    if not pool:
        raise RuntimeError(f"No voice IDs available for accent={accent} gender={gender}")
    # Prefer a voice nobody else in this test has, so two characters never share one.
    candidates = [v for v in pool if v not in used]
    if not candidates:
        # Pool exhausted (e.g. only 2 Canadian female voices): borrow an unused
        # voice of the same gender from another accent rather than reuse one.
        for acc, genders in config.ACCENT_GENDER_POOLS.items():
            candidates = [v for v in genders.get(gender, []) if v not in used]
            if candidates:
                break
    return rng.choice(candidates or pool)


def assign_test_voices(speaker_names, seed: int | None = None, profiles: dict | None = None) -> dict:
    """Returns {speaker_name: voice_id}, fixed for the whole test."""
    rng = random.Random(seed)
    assignment: dict = {}
    used: set = set()
    narrator_id = getattr(config, "NARRATOR_VOICE_ID", None)
    if narrator_id:
        used.add(narrator_id)          # reserved: no character ever gets the narrator's voice
    for speaker in sorted(set(speaker_names)):
        if narrator_id and speaker.upper() == "NARRATOR":
            assignment[speaker] = narrator_id
            continue
        profile = _profile_for(speaker, profiles)
        voice_id = _pick_voice_id(profile["accent"], profile["gender"], used, rng)
        assignment[speaker] = voice_id
        used.add(voice_id)
    return assignment


def collect_speakers(sections: dict) -> set:
    """sections: {section_num: [Segment, ...]} as returned by parser.parse_test."""
    speakers = set()
    for segs in sections.values():
        for seg in segs:
            for turn in seg.turns:
                if turn.kind in ("speech", "narrator"):
                    speakers.add(turn.speaker or "NARRATOR")
    return speakers