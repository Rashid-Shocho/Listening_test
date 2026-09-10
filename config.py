"""
Configuration for the IELTS Listening audio generation pipeline.

Speaker -> accent/gender profile, plus the accent+gender voice ID pools
(from 11labs_voiceID.xlsx) that voice_assignment.py randomly draws from
at the start of each test build. See voice_assignment.py for how a
specific voice_id gets picked and kept consistent for a speaker across
an entire test.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a local .env file (git-ignored) into os.environ, if present
except ImportError:
    pass  # python-dotenv not installed -> falls back to real env vars only

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
# Never hardcode a real key here. Set it via a local ".env" file (see
# .env.example) or an environment variable, e.g. in PowerShell:
#   $env:ELEVENLABS_API_KEY = "your-key-here"
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_v3")
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

# If no API key is present, the pipeline falls back to MOCK mode:
# it synthesizes silence of a plausible duration instead of real speech,
# so the whole assembly pipeline (silence/ambience/merge/export) can still
# be exercised end-to-end and validated before spending API credits.
MOCK_MODE = not bool(ELEVENLABS_API_KEY)

# Rewrite formal phrasing ("I will", "do not") to natural contractions
# ("I'll", "don't") in the text sent to the TTS API only -- never touches
# your stored script/answer-key text. Set False for verbatim delivery.
ENABLE_CONTRACTIONS = True

# ---------------------------------------------------------------------------
# Voice ID pools, by accent and gender -- from 11labs_voiceID.xlsx.
# 1 = male, 0 = female in the source sheet.
# voice_assignment.py randomly draws one voice_id per speaker (per test
# build) from the pool matching that speaker's SPEAKER_PROFILES entry.
# ---------------------------------------------------------------------------
ACCENT_GENDER_POOLS = {
    "British": {
        "male": [
            "Tx7VLgfksXHVnoY6jDGU", "aFyw0oiXW7dzKF4o7woX", "jRAAK67SEFE9m7ci5DhD",
            "llNlEi50DSCIEuoOIaH7", "bPwYieWFNPo6MSKrfS6j", "lUTamkMw7gOzZbFIwmq4",
            "ZVE5GaLwU3HuFONCXSPz", "P4DhdyNCB4Nl6MA0sL45", "fATgBRI8wg5KkDFg8vBd",
            "VsQmyFHffusQDewmHB5v",
        ],
        "female": [
            "kBag1HOZlaVBH7ICPE8x", "rqAWw1SQ1PYMM00B9ZTb", "1hlpeD1ydbI2ow0Tt3EW",
            "1YfmfuouRyRwVbpAZP7R", "Op72Fm6dzjYuyMTp6FBl", "HXOwtW4XU7Ne6iOiDHTl",
            "QqLi9iPR1Lu3I40qrGjU", "skNETUxpPRQlRrLwu88x",
        ],
    },
    "Australian": {
        "male": ["3DkcznWTIDSnX3f0J6DG", "gJaX474VQb1E5GJBSCPh", "QLOrGSLtlFUlfQRSaOtQ"],
        "female": [
            "ssxGjYJjpi2zZlztJhZU", "319bKIhetA5g6tmywrwj", "rSeWUeOepJe3YA3pacAe",
            "tyZ2vPoArunQ8LpRQu6x", "Bu8XtNMginOxwiByyW2I", "TvYCW7acMEs9RZ2kkcBn",
            "U9VgC8Xinl7nnNsyDd3J",
        ],
    },
    "Canadian": {
        "male": [
            "DMljQdXAGELCjF2K6UHK", "klfO7uDt4WsjhNnhI2HZ", "y26Xv4PQ7Ftbu1mfaEFY",
            "lAyepFdMFNSZ30LU9edN", "bBE6oKIBXZhM23o3YoXb", "mI8xLTBNjMXAf31I4xlB",
            "w4Z9gYJrajAuQmheNbVn", "epkQ8pqDcY2DxhmFi8xl", "ZN36quYSeOCuxo0IhFKk",
            "frBOG9T06d0Zw1PEvoZN",
        ],
        "female": ["JpjuQfOymR78GvGgYe0U", "ClKfJnuqp0hQ7Ax41F4w"],
    },
    "American": {
        "male": [
            "wBXNqKUATyqu0RtYt25i", "s3TPKV1kjDlVtZbl4Ksh", "8Ln42OXYupYsag45MAUy",
            "ev2kMR9ZJZZsemuogS5u", "pVnrL6sighQX7hVz89cp", "J2FGlQG8Gd7x8uEDt2H8",
            "1IKfgBmzdwnmAUPnryb3",
        ],
        "female": [
            "k9KXsQFJqzAoomTCOrJB", "xFPwxsyzPJFEaL61n2ms", "PStJ2DzQnh8zxG5PDf1s",
            "KWDD3Wyq30ZF5NEL01EJ", "rCuVrCHOUMY3OwyJBJym", "LJwPgeJYv0dNJzEtXVO6",
            "Fc5CaIGWKvLHapoOSM2K", "K7W7zLWeGoxU9YqWoB7A", "DODLEQrClDo8wCz460ld",
            "mC104ON19u9NruNfYC3j",
        ],
    },
}

# ---------------------------------------------------------------------------
# Speaker -> accent/gender profile. voice_assignment.py uses this (not a
# fixed voice_id) to decide which pool to draw a random voice from.
# accent must be one of the ACCENT_GENDER_POOLS keys above.
# ---------------------------------------------------------------------------
SPEAKER_PROFILES = {
    "narrator": {"accent": "British", "gender": "female", "desc": "Neutral IELTS narrator"},
    # TEST1 -- Mock Test 1, trimmed emotive edition
    "Emma": {"accent": "Australian", "gender": "female", "desc": "Community arts centre receptionist"},
    "Daniel": {"accent": "British", "gender": "male", "desc": "Prospective class member"},
    "Claire": {"accent": "Canadian", "gender": "female", "desc": "Museum guide"},
    "Dr. Morris": {"accent": "British", "gender": "female", "desc": "University supervisor"},
    "Adam": {"accent": "Australian", "gender": "male", "desc": "Student"},
    "Sofia": {"accent": "American", "gender": "female", "desc": "Student"},
    "Lecturer": {"accent": "British", "gender": "male", "desc": "Section 4 lecturer"},
    # TEST2 -- sample data shipped in the repo
    "Mark": {"accent": "American", "gender": "male", "desc": "Sports centre receptionist"},
    "Nina": {"accent": "American", "gender": "female", "desc": "Prospective member"},
    "Visitor Information Officer": {"accent": "American", "gender": "female", "desc": "Heritage centre officer"},
    "Professor Bennett": {"accent": "Canadian", "gender": "male", "desc": "University supervisor"},
    "Alex": {"accent": "Canadian", "gender": "male", "desc": "Student"},
    "Maya": {"accent": "Canadian", "gender": "female", "desc": "Student"},
    "University Lecturer": {"accent": "American", "gender": "male", "desc": "Section 4 lecturer"},
}

DEFAULT_PROFILE = {"accent": "British", "gender": "female", "desc": "Fallback voice for an unlisted speaker"}

# ElevenLabs voice_settings applied to every line. With Eleven v3, actual
# emotional/contextual delivery comes from [tags] embedded directly in the
# text (see tts_client._tagged_text) -- these settings just control how
# much the model can vary from the base voice around that direction.
# Lower stability = more expressive/variable (can sound more "alive" and
# less robotic); higher stability = flatter, more monotone, more robotic.
# 0.30-0.35 is a good starting point for natural, non-robotic delivery.
DEFAULT_VOICE_SETTINGS = {
    "stability": 0.32,
    "similarity_boost": 0.85,
    "style": 0.55,
    "use_speaker_boost": True,
}

# Deprecated: no longer used (multi-word tags like "warm, welcoming" never
# matched these single-word keys, so every line silently fell back to
# "default" regardless of context -- that was the source of the flat,
# robotic delivery). Kept only so nothing else importing this breaks.
TAG_SETTINGS = {"default": DEFAULT_VOICE_SETTINGS}

# Per-voice_id overrides. If a specific voice sounds flat/robotic no
# matter what tags it's given (some voices just don't respond much to
# eleven_v3 emotion tags), add its voice_id here with more aggressive
# settings instead of touching DEFAULT_VOICE_SETTINGS for everyone.
# Example, after identifying a weak female voice_id in the Voice Lab:
#   VOICE_SETTINGS_OVERRIDES = {
#       "kBag1HOZlaVBH7ICPE8x": {"stability": 0.20, "similarity_boost": 0.80,
#                                  "style": 0.75, "use_speaker_boost": True},
#   }
VOICE_SETTINGS_OVERRIDES: dict[str, dict] = {}

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

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------
# "30 SECONDS OF SILENCE" markers in the source scripts are skipped entirely
# -- no dead air is inserted anywhere in the generated audio.
GAP_BETWEEN_TURNS_MS = 450          # natural pause between speaker turns
GAP_AFTER_NARRATOR_MS = 700

OUTPUT_DIR = "output"
CACHE_DIR = "cache"