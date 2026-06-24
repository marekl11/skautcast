"""Gemini TTS backend (Google AI Studio) — free tier, native Czech, and the
speaking style is promptable. Returns a WAV (24 kHz mono PCM) which build.py
then encodes to mp3.
"""
import base64
import time
import wave
from pathlib import Path

import requests

from . import config

API = "https://generativelanguage.googleapis.com/v1beta/models"


def _pcm_to_wav(pcm: bytes, path: Path, rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes(pcm)


def synth_wav(text: str, wav_path: Path) -> Path:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set (env var or .gemini_key file).")
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    style = getattr(config, "GEMINI_STYLE", "")
    prompt = f"{style}\n\n{text}" if style else text

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": config.GEMINI_VOICE}
                }
            },
        },
    }
    url = f"{API}/{config.GEMINI_TTS_MODEL}:generateContent"

    # Retry with backoff on rate limits / transient errors (free tier is rate-limited).
    for attempt in range(5):
        resp = requests.post(url, params={"key": config.GEMINI_API_KEY},
                             json=body, timeout=180)
        if resp.status_code == 200:
            break
        if resp.status_code in (429, 500, 503) and attempt < 4:
            wait = 2 ** attempt * 3  # 3, 6, 12, 24s
            print(f"  [gemini] {resp.status_code}, retrying in {wait}s ...", flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(f"Gemini TTS {resp.status_code}: {resp.text[:300]}")

    part = resp.json()["candidates"][0]["content"]["parts"][0]
    pcm = base64.b64decode(part["inlineData"]["data"])
    _pcm_to_wav(pcm, wav_path)
    return wav_path
