"""
Thin wrapper around the ElevenLabs text-to-speech REST API, with a MOCK
fallback (a quiet placeholder hum of plausible duration) so the rest of the
pipeline can be tested without spending API credits.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time

import requests
from pydub import AudioSegment
from pydub.generators import Sine

import config


def _apply_contractions(text: str) -> str:
    """Conservative contraction pass on the text sent to the API only."""
    if not config.ENABLE_CONTRACTIONS:
        return text

    pairs = [
        (r"\bwill not\b", "won't"), (r"\bcannot\b", "can't"), (r"\bcan not\b", "can't"),
        (r"\bdo not\b", "don't"), (r"\bdoes not\b", "doesn't"), (r"\bdid not\b", "didn't"),
        (r"\bwould not\b", "wouldn't"), (r"\bshould not\b", "shouldn't"),
        (r"\bis not\b", "isn't"), (r"\bare not\b", "aren't"), (r"\bwas not\b", "wasn't"),
        (r"\bwere not\b", "weren't"), (r"\bhave not\b", "haven't"), (r"\bhas not\b", "hasn't"),
        (r"\bI will\b", "I'll"), (r"\bI am\b", "I'm"), (r"\bI have\b", "I've"),
        (r"\bI would\b", "I'd"), (r"\byou will\b", "you'll"), (r"\byou are\b", "you're"),
        (r"\byou have\b", "you've"), (r"\bwe will\b", "we'll"), (r"\bwe are\b", "we're"),
        (r"\bwe have\b", "we've"), (r"\bthey will\b", "they'll"), (r"\bthey are\b", "they're"),
        (r"\bhe will\b", "he'll"), (r"\bshe will\b", "she'll"), (r"\bit will\b", "it'll"),
        (r"\bit is\b", "it's"), (r"\bthat is\b", "that's"), (r"\bthat will\b", "that'll"),
        (r"\blet us\b", "let's"), (r"\bthere is\b", "there's"), (r"\bwho is\b", "who's"),
    ]

    def _repl(pattern, repl, s):
        def match_case(m):
            word = m.group(0)
            if word[0].isupper():
                return repl[0].upper() + repl[1:]
            return repl
        return re.sub(pattern, match_case, s, flags=re.IGNORECASE)

    for pattern, repl in pairs:
        text = _repl(pattern, repl, text)
    return text


def _cache_path(cache_dir: str, key: str) -> str:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(cache_dir, f"{h}.mp3")


def _voice_settings(voice_id: str | None = None) -> dict:
    if voice_id and voice_id in config.VOICE_SETTINGS_OVERRIDES:
        return config.VOICE_SETTINGS_OVERRIDES[voice_id]
    return config.DEFAULT_VOICE_SETTINGS


def _seed_for(voice_id: str | None) -> int | None:
    if voice_id and voice_id == getattr(config, "NARRATOR_VOICE_ID", None):
        return getattr(config, "NARRATOR_SEED", None)
    return None


def _tagged_text(text: str, tag: str | None) -> str:
    """Contractions + only the safe v3 tags (see config.SAFE_OUTPUT_TAGS)."""
    text = _apply_contractions(text)
    if not tag:
        return text
    raw_parts = [p.strip() for p in tag.split(",") if p.strip()]
    mapped = []
    for p in raw_parts:
        m = config._map_one_tag(p)
        if m and m not in mapped:
            mapped.append(m)
    if not mapped:
        return text
    prefix = "".join(f"[{p}]" for p in mapped)
    return f"{prefix} {text}"


def synthesize_line(text: str, voice_id: str, tag: str | None, cache_dir: str) -> AudioSegment:
    """
    Returns an AudioSegment for one request. Cached on disk, keyed on voice,
    tag, text, model and voice settings -- so changing settings or model
    re-synthesizes instead of silently reusing old clips.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = (f"{voice_id}::{tag}::{text}::ct{int(config.ENABLE_CONTRACTIONS)}"
                 f"::{config.ELEVENLABS_MODEL_ID}::{json.dumps(_voice_settings(voice_id), sort_keys=True)}"
                 f"::seed{_seed_for(voice_id)}::mock{int(config.MOCK_MODE)}")
    path = _cache_path(cache_dir, cache_key)

    if os.path.exists(path):
        return AudioSegment.from_file(path)

    if config.MOCK_MODE:
        audio = _mock_tts(text)
    else:
        audio = _elevenlabs_tts(text, voice_id, tag)

    audio.export(path, format="mp3")
    return audio


def _mock_tts(text: str) -> AudioSegment:
    words = max(1, len(re.sub(r"\[[^\]]*\]", "", text).split()))
    seconds = max(0.5, words / 2.5)  # ~150 wpm
    ms = int(seconds * 1000)
    return Sine(90).to_audio_segment(duration=ms).apply_gain(-45)


def _elevenlabs_tts(text: str, voice_id: str, tag: str | None) -> AudioSegment:
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    url = f"{config.ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": _tagged_text(text, tag) if tag else text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": _voice_settings(voice_id),
    }
    seed = _seed_for(voice_id)
    if seed is not None:
        payload["seed"] = seed

    max_attempts = 5
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            wait = min(2 ** attempt, 20)
            print(f"    [retry {attempt}/{max_attempts}] network error, retrying in {wait}s: {e}")
            time.sleep(wait)
            continue

        if resp.status_code == 429:
            wait = min(5 * attempt, 30)
            print(f"    [retry {attempt}/{max_attempts}] rate limited (429), retrying in {wait}s")
            time.sleep(wait)
            continue

        if not resp.ok:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            raise RuntimeError(f"ElevenLabs API error {resp.status_code} for voice {voice_id}: {detail}")

        return AudioSegment.from_file(io.BytesIO(resp.content), format="mp3")

    raise RuntimeError(f"ElevenLabs request failed after {max_attempts} attempts: {last_err}")