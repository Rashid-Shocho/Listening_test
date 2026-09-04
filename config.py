"""
Configuration for the IELTS Listening audio generation pipeline.

Maps speaker names -> ElevenLabs voice_id + accent, per test.
Edit VOICE_MAP to point at real ElevenLabs voice IDs from your account.
(voice.elevenlabs.io -> Voice Library -> copy Voice ID)
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
# Voice mapping: speaker name -> (voice_id, accent, gender) per accent pool.
# Fill in real ElevenLabs voice IDs here. Placeholder IDs are used in mock
# mode and will simply be ignored.
# ---------------------------------------------------------------------------
VOICE_POOL = {
    "narrator": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "accent": "en-GB", "desc": "Neutral IELTS narrator"},
    # Test 1
    "Emily": {"voice_id": "EXAVITQu4vr4xnSDxMaL", "accent": "en-GB", "desc": "Female, warm, British"},
    "Daniel": {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "accent": "en-GB", "desc": "Male, British"},
    "Guide": {"voice_id": "XB0fDUnXU5powFXDhCwa", "accent": "en-AU", "desc": "Female, Australian"},
    "Dr. Harris": {"voice_id": "onwK4e9ZLuTAKqWW03F9", "accent": "en-GB", "desc": "Male/Female supervisor"},
    "Liam": {"voice_id": "pNInz6obpgDQGcFmaJgB", "accent": "en-GB", "desc": "Male, British"},
    "Sofia": {"voice_id": "ThT5KcBeYPX3keUQqHPh", "accent": "en-GB", "desc": "Female, British"},
    "Lecturer": {"voice_id": "flq6f7yk4E4fJM5XTYuZ", "accent": "en-GB", "desc": "Male/Female lecturer"},
    # Test 2
    "Mark": {"voice_id": "VR6AewLTigWG4xSOukaG", "accent": "en-US", "desc": "Male, American"},
    "Nina": {"voice_id": "jsCqWAovK2LkecY7zXl4", "accent": "en-US", "desc": "Female, American"},
    "Visitor Information Officer": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "accent": "en-US", "desc": "Female, American"},
    "Professor Bennett": {"voice_id": "onwK4e9ZLuTAKqWW03F9", "accent": "en-CA", "desc": "Male/Female, Canadian"},
    "Alex": {"voice_id": "pNInz6obpgDQGcFmaJgB", "accent": "en-CA", "desc": "Male, Canadian"},
    "Maya": {"voice_id": "ThT5KcBeYPX3keUQqHPh", "accent": "en-CA", "desc": "Female, Canadian"},
    "University Lecturer": {"voice_id": "flq6f7yk4E4fJM5XTYuZ", "accent": "en-US", "desc": "Lecturer, American"},
}

DEFAULT_VOICE = {"voice_id": "21m00Tcm4TlvDq8ikWAM", "accent": "en-GB", "desc": "Fallback narrator voice"}

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