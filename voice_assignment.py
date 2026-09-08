"""
Randomized-but-consistent voice assignment.

Each speaker appearing anywhere in a test is assigned exactly one random
voice_id -- drawn from config.ACCENT_GENDER_POOLS using that speaker's
accent/gender in config.SPEAKER_PROFILES -- once, at the start of that
test's build. That same voice_id is then reused for every line that
speaker has anywhere in the test (every section it appears in), so no
one's voice drifts or swaps mid-test. The narrator gets one voice for
the whole test the same way everyone else does.

Two different tests, or two runs of the same test, get freshly randomized
voices by default (nothing is hardcoded) -- pass `seed` if you want a
specific run to be reproducible.
"""

from __future__ import annotations

import random

import config


def _profile_for(speaker: str) -> dict:
    if speaker in config.SPEAKER_PROFILES:
        return config.SPEAKER_PROFILES[speaker]
    lower = speaker.lower()
    for name, profile in config.SPEAKER_PROFILES.items():
        if name.lower() == lower:
            return profile
    return config.DEFAULT_PROFILE


def _pick_voice_id(accent: str, gender: str, used: set) -> str:
    pool = config.ACCENT_GENDER_POOLS.get(accent, {}).get(gender, [])
    if not pool:
        # That accent/gender combo is empty in the sheet (e.g. Canadian
        # female only has 2 entries) -- fall back to the other gender in
        # the same accent rather than crashing.
        other = "female" if gender == "male" else "male"
        pool = config.ACCENT_GENDER_POOLS.get(accent, {}).get(other, [])
    if not pool:
        pool = config.ACCENT_GENDER_POOLS.get("British", {}).get(gender, [])
    if not pool:
        raise RuntimeError(f"No voice IDs available anywhere for accent={accent} gender={gender}")

    # Prefer a voice nobody else in this test already has, so two
    # characters don't end up sounding identical by chance -- but don't
    # hard-fail if the cast is bigger than the pool.
    candidates = [v for v in pool if v not in used] or pool
    return random.choice(candidates)


def assign_test_voices(speaker_names, seed: int | None = None) -> dict:
    """
    speaker_names: iterable of every speaker string that appears anywhere
    in the test (as literally written in the parsed turns, e.g. "NARRATOR",
    "Emma", "Dr. Morris").

    Returns {speaker_name: voice_id} -- one fixed voice per speaker, valid
    for the whole test regardless of how many sections they appear in.
    """
    prior_state = random.getstate()
    if seed is not None:
        random.seed(seed)
    try:
        assignment: dict = {}
        used: set = set()
        for speaker in sorted(set(speaker_names)):
            profile = _profile_for(speaker)
            voice_id = _pick_voice_id(profile["accent"], profile["gender"], used)
            assignment[speaker] = voice_id
            used.add(voice_id)
        return assignment
    finally:
        if seed is not None:
            random.setstate(prior_state)


def collect_speakers(sections: dict) -> set:
    """sections: {section_num: [Segment, ...]} as returned by parser.parse_test."""
    speakers = set()
    for segs in sections.values():
        for seg in segs:
            for turn in seg.turns:
                if turn.kind in ("speech", "narrator"):
                    speakers.add(turn.speaker or "NARRATOR")
    return speakers
