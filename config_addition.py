# ---------------------------------------------------------------------------
# Eleven v3 tag safety.
#
# Your scripts' delivery tags (e.g. "measured, cautionary", "explaining,
# adjusting", "content, brief", "a little tentative") were written as
# free-form director's notes for a human voice actor -- NOT as literal
# Eleven v3 audio tags. v3 only recognizes a specific trained vocabulary
# (a subset of the emotions/actions below). Sending it an unrecognized
# bracketed string like "[explaining][adjusting]" or "[a little
# tentative]" has undefined behavior -- at best it's silently ignored, at
# worst the model can misread it as a speaker/scene-change cue (v3 was
# also trained on multi-character scripts using bracket syntax), which is
# a plausible concrete mechanism for an unexpected extra voice appearing
# mid-clip even though the actual script only specifies your real cast.
#
# TAG_ALIAS_MAP maps a script tag (lowercased) to the nearest real,
# recognized v3 tag. Anything NOT in this map is dropped entirely rather
# than forwarded verbatim -- better to fall back to plain stability/style
# delivery for an unmapped tag than risk sending v3 an unrecognized
# bracketed token. Extend this map as you identify more useful matches.
SUPPORTED_V3_TAGS = {
    "happy", "sad", "angry", "excited", "curious", "surprised", "scared",
    "whispers", "shouts", "sighs", "laughs", "crying", "sarcastic",
    "mischievously", "nervous", "confident", "tired", "disgusted",
}

TAG_ALIAS_MAP = {
    "warm": None, "welcoming": "happy", "friendly": "happy",
    "helpful": None, "curious": "curious", "thoughtful": None,
    "encouraging": "happy", "pleased": "happy", "delighted": "excited",
    "confirming": None, "hopeful": "excited", "precise": None,
    "acknowledging": None, "informative": None, "descriptive": None,
    "reassuring": None, "surprised": "surprised", "accepting": None,
    "decisive": None, "satisfied": "happy", "brisk": None,
    "businesslike": None, "careful": None, "calculating": None,
    "relieved": "happy", "apologetic": "sad", "grateful": "happy",
    "closing": None, "concluding": None, "warm, closing": None,
    "clear": None, "matter-of-fact": None, "steady": None, "guiding": None,
    "confident": "confident", "presenting": None, "proud": "confident",
    "reflective": None, "gentle": None, "cautionary": "nervous",
    "transitional": None, "engaging": "excited", "contrasting": None,
    "explanatory": None, "measured": None, "emphatic": None,
    "impressed": "surprised", "balanced": None, "forward-looking": None,
    "illustrative": None, "rhetorical": None, "intrigued": "curious",
    "warm, engaging": "happy", "organizing": None, "probing": "curious",
    "recalling": None, "conceding": None, "explaining": None,
    "adjusting": None, "disagreeing": None, "firm": "angry",
    "gently teasing": "mischievously", "brief": None, "content": "happy",
    "calm": None, "final": None, "announcer": None, "quick": None,
    "considering": None, "agreeing": None, "hesitant": "nervous",
    "tentative": "nervous", "a little tentative": "nervous",
    "friendly, a little tentative": "nervous",
}


def _map_one_tag(raw: str) -> str | None:
    key = raw.strip().lower()
    if key in TAG_ALIAS_MAP:
        return TAG_ALIAS_MAP[key]
    if key in SUPPORTED_V3_TAGS:
        return key
    return None