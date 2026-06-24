"""ElevenLabs TTS backend — studio-quality cloud synthesis.

Used when config.TTS_BACKEND == "elevenlabs". Returns a finished mp3 directly
(no local cleanup needed). ElevenLabs handles Czech numbers/abbreviations and
prosody itself, so the text is sent as-is.
"""
from pathlib import Path

import requests

from . import config

API_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def synth_mp3(text: str, mp3_path: Path) -> Path:
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not set (env var or .elevenlabs_key file).")
    if not config.ELEVENLABS_VOICE_ID:
        raise RuntimeError("ELEVENLABS_VOICE_ID not set in config.")

    mp3_path = Path(mp3_path)
    mp3_path.parent.mkdir(parents=True, exist_ok=True)

    resp = requests.post(
        f"{API_URL}/{config.ELEVENLABS_VOICE_ID}",
        params={"output_format": config.ELEVENLABS_OUTPUT_FORMAT},
        headers={"xi-api-key": config.ELEVENLABS_API_KEY,
                 "Content-Type": "application/json"},
        json={"text": text,
              "model_id": config.ELEVENLABS_MODEL,
              "voice_settings": config.ELEVENLABS_VOICE_SETTINGS},
        timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs API {resp.status_code}: {resp.text[:300]}")
    mp3_path.write_bytes(resp.content)
    return mp3_path
