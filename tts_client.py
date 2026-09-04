"""
Thin wrapper around the ElevenLabs text-to-speech REST API, with a MOCK
fallback (silence of a plausible duration) so the rest of the pipeline can
be developed/tested without burning API credits or requiring network
access to elevenlabs.io from this environment.
"""

from __future__ import annotations

import hashlib
import io
import os
import time

import requests
from pydub import AudioSegment
from pydub.generators import Sine

import config


def _cache_path(cache_dir: str, key: str) -> str:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(cache_dir, f"{h}.mp3")


def _voice_settings_for_tag(tag: str | None) -> dict:
    return config.TAG_SETTINGS.get((tag or "").lower(), config.TAG_SETTINGS["default"])


def synthesize_line(text: str, speaker: str, tag: str | None, cache_dir: str) -> AudioSegment:
    """
    Returns an AudioSegment for one line of dialogue/narration. Uses a
    filesystem cache keyed on (speaker, tag, text, voice_id) so re-running
    the pipeline doesn't re-synthesize unchanged lines.
    """
    os.makedirs(cache_dir, exist_ok=True)
    voice = config.VOICE_POOL.get(speaker, config.DEFAULT_VOICE)
    cache_key = f"{voice['voice_id']}::{tag}::{text}"
    path = _cache_path(cache_dir, cache_key)

    if os.path.exists(path):
        return AudioSegment.from_file(path)

    if config.MOCK_MODE:
        audio = _mock_tts(text)
    else:
        audio = _elevenlabs_tts(text, voice["voice_id"], tag)

    audio.export(path, format="mp3")
    return audio


def _mock_tts(text: str) -> AudioSegment:
    """
    Stand-in for real speech: silent clip whose duration approximates how
    long the line would take to speak (~150 words/min, floor 500ms), so
    downstream timing/assembly logic can be validated realistically.
    """
    words = max(1, len(text.split()))
    seconds = max(0.5, words / 2.5)  # ~150 wpm
    ms = int(seconds * 1000)
    # Use near-silent low hum instead of dead silence so it's audible in
    # a scrub-through QA pass that this *is* a placeholder, not a bug.
    tone = Sine(90).to_audio_segment(duration=ms).apply_gain(-45)
    return tone


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
        "text": text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": _voice_settings_for_tag(tag),
    }

    max_attempts = 5
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=90)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Transient network blip (connection reset, timeout, etc.) --
            # back off and retry rather than aborting the whole run.
            last_err = e
            wait = min(2 ** attempt, 20)
            print(f"    [retry {attempt}/{max_attempts}] network error, retrying in {wait}s: {e}")
            time.sleep(wait)
            continue

        if resp.status_code == 429:
            # Rate limited -- back off longer and retry.
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