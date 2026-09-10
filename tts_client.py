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
import re
import time

import requests
from pydub import AudioSegment
from pydub.generators import Sine

import config


def _apply_contractions(text: str) -> str:
    """
    Light, safe contraction pass applied only to the text sent to the TTS
    API -- never touches the stored script/answer-key text. Improves
    natural speech flow ("I'll" instead of "I will") without risking the
    exact-wording integrity your scripts are QC'd for, since this only
    happens at synthesis time on a throwaway copy of the string.

    Deliberately conservative: only common, unambiguous contractions,
    matched whole-word and case-preserving. Skip this by setting
    config.ENABLE_CONTRACTIONS = False if you ever need verbatim delivery
    (e.g. a line where "will not" needs the emphasis "will" carries).
    """
    if not config.ENABLE_CONTRACTIONS:
        return text

    pairs = [
        # Negations first -- must run before the plain "subject will/are/have"
        # rules below, or e.g. "we will not" gets mangled into "we'll not"
        # instead of "we won't" (the plain rule fires first and consumes
        # "will" before the negative pattern ever sees it).
        (r"\bwill not\b", "won't"), (r"\bcannot\b", "can't"), (r"\bcan not\b", "can't"),
        (r"\bdo not\b", "don't"), (r"\bdoes not\b", "doesn't"), (r"\bdid not\b", "didn't"),
        (r"\bwould not\b", "wouldn't"), (r"\bshould not\b", "shouldn't"),
        (r"\bis not\b", "isn't"), (r"\bare not\b", "aren't"), (r"\bwas not\b", "wasn't"),
        (r"\bwere not\b", "weren't"), (r"\bhave not\b", "haven't"), (r"\bhas not\b", "hasn't"),
        # Plain subject contractions
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
    """
    Settings profile for a line. Eleven v3's actual expressiveness comes
    mainly from the [tags] embedded in the text (see _tagged_text below),
    not from stability/style alone -- but not every voice_id responds to
    those tags equally well. Some voices (especially older/IVC ones) stay
    flat regardless of tags; if you find one of those, add its voice_id to
    config.VOICE_SETTINGS_OVERRIDES to push it harder (lower stability,
    higher style) without changing every other voice's settings.
    """
    if voice_id and voice_id in config.VOICE_SETTINGS_OVERRIDES:
        return config.VOICE_SETTINGS_OVERRIDES[voice_id]
    return config.DEFAULT_VOICE_SETTINGS


def _tagged_text(text: str, tag: str | None) -> str:
    """
    Eleven v3 reads performance direction from a specific trained
    vocabulary of tags written directly in the input text, e.g.
    "[happy] Good morning, ...". Your script's tags are free-form
    director's notes ("warm, welcoming", "measured, cautionary",
    "a little tentative"), most of which are NOT real v3 tags -- forwarding
    them verbatim has undefined behavior and is a plausible cause of
    unexpected artifacts (including an extra voice appearing) since v3 can
    misread an unrecognized bracketed token as a scene/speaker cue rather
    than a delivery direction. Only tags that map to config.TAG_ALIAS_MAP's
    known-safe v3 vocabulary are sent; anything else is dropped and the
    line is synthesized with plain delivery (stability/style still apply).
    """
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
    Returns an AudioSegment for one line of dialogue/narration. Uses a
    filesystem cache keyed on (voice_id, tag, text) so re-running the
    pipeline doesn't re-synthesize unchanged lines. voice_id is resolved
    by the caller (see voice_assignment.py) -- one fixed voice per speaker
    for the whole test, not looked up per-line here.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_key = f"{voice_id}::{tag}::{text}::ct{int(config.ENABLE_CONTRACTIONS)}"
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
        "text": _tagged_text(text, tag),
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": _voice_settings(voice_id),
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