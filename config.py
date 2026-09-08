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

# ElevenLabs voice_settings per delivery tag family (rough emotional mapping).
# v3 supports more expressive control; stability/similarity approximate it.
TAG_SETTINGS = {
    "default": {"stability": 0.45, "similarity_boost": 0.80, "style": 0.30},
    "warm": {"stability": 0.40, "similarity_boost": 0.80, "style": 0.45},
    "hesitant": {"stability": 0.35, "similarity_boost": 0.78, "style": 0.35},
    "curious": {"stability": 0.42, "similarity_boost": 0.80, "style": 0.35},
    "reassuring": {"stability": 0.45, "similarity_boost": 0.82, "style": 0.30},
    "practical": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.20},
    "clear": {"stability": 0.50, "similarity_boost": 0.82, "style": 0.15},
    "quick": {"stability": 0.38, "similarity_boost": 0.78, "style": 0.40},
    "confident": {"stability": 0.48, "similarity_boost": 0.82, "style": 0.30},
    "agreeing": {"stability": 0.45, "similarity_boost": 0.80, "style": 0.25},
    "considering": {"stability": 0.42, "similarity_boost": 0.80, "style": 0.30},
    "thoughtful": {"stability": 0.42, "similarity_boost": 0.80, "style": 0.30},
    "grateful": {"stability": 0.45, "similarity_boost": 0.82, "style": 0.35},
    "soft": {"stability": 0.50, "similarity_boost": 0.82, "style": 0.20},
    "concluding": {"stability": 0.50, "similarity_boost": 0.82, "style": 0.20},
    "measured": {"stability": 0.55, "similarity_boost": 0.82, "style": 0.15},
    "reflective": {"stability": 0.50, "similarity_boost": 0.82, "style": 0.25},
}

# ---------------------------------------------------------------------------
# Timing / audio constants
# ---------------------------------------------------------------------------
SILENCE_MARKER_MS = 30_000          # "30 SECONDS OF SILENCE" production marker
GAP_BETWEEN_TURNS_MS = 450          # natural pause between speaker turns
GAP_AFTER_NARRATOR_MS = 700
AMBIENCE_DB_RELATIVE = -23          # target ambience level relative to speech (approx -22 to -24dB)
CROSSFADE_MS = 300                  # crossfade between merged section files

# Ambience beds: section -> generated/looped background file (wav) in ./ambience/
# You may replace these with real room-tone recordings. If absent, the
# pipeline auto-generates soft pink-noise-like ambience as a stand-in.
AMBIENCE_DESCRIPTIONS = {
    1: "Quiet community arts-centre / sports-centre reception. Room tone, faint footsteps.",
    2: "Quiet library / heritage-centre foyer. Room tone, occasional footsteps.",
    3: "Quiet university seminar room. Faint ventilation, paper movement.",
    4: "Quiet university lecture theatre. Low HVAC, occasional chair movement.",
}

OUTPUT_DIR = "output"
CACHE_DIR = "cache"
AMBIENCE_DIR = "ambience"
