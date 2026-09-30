"""Gemini TTS backend (Google AI Studio) — free tier, native Czech, and the
speaking style is promptable. Returns a WAV (24 kHz mono PCM) which build.py
then encodes to mp3.
"""
import base64
import hashlib
import time
import wave
from pathlib import Path

import numpy as np
import requests

from . import config

API = "https://generativelanguage.googleapis.com/v1beta/models"
# Finished parts, so a build stopped half-way (say, by the free tier's daily limit)
# picks up where it left off instead of paying for the same parts again.
PART_CACHE = config.DATA / "_wav" / "parts"


def _pcm_to_wav(pcm: bytes, path: Path, rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes(pcm)


def _parts(text: str, limit: int) -> list[str]:
    """Split `text` at line breaks into parts of at most `limit` characters. A single
    paragraph longer than that stays whole rather than being cut mid-sentence."""
    parts, cur = [], ""
    for para in text.split("\n"):
        if cur and len(cur) + 1 + len(para) > limit:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def synth_wav(text: str, wav_path: Path, voice: str | None = None,
              style: str | None = None) -> Path:
    """Synthesize `text` to a 24 kHz mono WAV. `style` overrides GEMINI_STYLE when
    given (pass "" to read the text plainly, e.g. for the AI notice); None falls
    back to the configured podcast style. Text longer than GEMINI_MAX_CHARS is read
    in several requests, joined by GEMINI_PART_GAP_MS of silence, and a part that
    rings is read again (see _clean_take)."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set (env var or .gemini_key file).")
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    voice = voice or config.GEMINI_VOICE

    if style is None:
        style = getattr(config, "GEMINI_STYLE", "")
    parts = _parts(text, config.GEMINI_MAX_CHARS)
    gap = b"\x00\x00" * (24000 * config.GEMINI_PART_GAP_MS // 1000)  # 16-bit silence
    pcm = []
    for i, part in enumerate(parts, 1):
        if len(parts) > 1:
            print(f"  [gemini] part {i}/{len(parts)} ({len(part)} chars)", flush=True)
        pcm.append(_clean_take(part, voice, style))
    _pcm_to_wav(gap.join(pcm), wav_path)
    return wav_path


def _clean_take(text: str, voice: str, style: str) -> bytes:
    """Read `text`, reading it again (up to GEMINI_TAKES times in all) while the take
    rings, and return the cleanest take. Finished parts are kept in PART_CACHE."""
    key = f"{config.GEMINI_TTS_MODEL}|{voice}|{style}|{text}"
    cached = PART_CACHE / f"{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}.pcm"
    if cached.exists():
        return cached.read_bytes()
    best, best_db = b"", None
    for take in range(1, config.GEMINI_TAKES + 1):
        pcm = _synth_pcm(text, voice, style)
        ring = _ringing_db(pcm)
        if best_db is None or ring < best_db:
            best, best_db = pcm, ring
        if ring <= config.GEMINI_MAX_RINGING_DB:
            break
        print(f"  [gemini] take {take} rings ({ring:.1f} dB)"
              + (", reading it again ..." if take < config.GEMINI_TAKES else ", keeping the cleanest"),
              flush=True)
    PART_CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(best)
    return best


def _ringing_db(pcm: bytes, rate: int = 24000) -> float:
    """How much Gemini rings in `pcm`: the metallic, telephone-like tone it slips into
    now and then, which shows up as steady lines across the spectrum that speech never
    holds that long. For each 10 s stretch, the median spectrum (over time) is compared
    with a running median across frequency, which follows the voice but not a narrow
    line; the result is how far the 10 strongest lines in 2–10 kHz stick out, in dB,
    for the worst stretch."""
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    nfft, hop, win = 2048, 512, 10 * rate
    freqs = np.fft.rfftfreq(nfft, 1 / rate)
    band = (freqs >= 2000) & (freqs <= 10000)
    worst = 0.0
    for start in range(0, len(x), win):
        stretch = x[start:start + win]
        if len(stretch) < 3 * rate:  # too short to tell a held tone from a vowel
            continue
        frames = np.lib.stride_tricks.sliding_window_view(stretch, nfft)[::hop] * np.hanning(nfft)
        spec = 10 * np.log10(np.median(np.abs(np.fft.rfft(frames, axis=1)) ** 2, axis=0) + 1e-20)
        voice = np.median(np.lib.stride_tricks.sliding_window_view(np.pad(spec, 15, mode="edge"), 31), axis=1)
        worst = max(worst, float(np.sort((spec - voice)[band])[-10:].mean()))
    return worst


def _synth_pcm(text: str, voice: str, style: str) -> bytes:
    """One Gemini TTS request: `text` read in `voice`, returned as raw 24 kHz PCM."""
    prompt = f"{style}\n\n{text}" if style else text

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice}
                }
            },
        },
    }
    url = f"{API}/{config.GEMINI_TTS_MODEL}:generateContent"

    # Retry with backoff on rate limits / transient errors (free tier is rate-limited).
    # Network faults are retried too: a single read timeout used to abort a whole
    # batch run part-way through, throwing away nothing but costing a restart.
    for attempt in range(5):
        try:
            resp = requests.post(url, params={"key": config.GEMINI_API_KEY},
                                 json=body, timeout=180)
        except requests.RequestException as exc:
            if attempt == 4:
                raise RuntimeError(f"Gemini TTS unreachable: {exc}") from exc
            wait = 2 ** attempt * 3
            print(f"  [gemini] {type(exc).__name__}, retrying in {wait}s ...", flush=True)
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            break
        if resp.status_code in (429, 500, 503) and attempt < 4:
            wait = 2 ** attempt * 3  # 3, 6, 12, 24s
            print(f"  [gemini] {resp.status_code}, retrying in {wait}s ...", flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(f"Gemini TTS {resp.status_code}: {resp.text[:300]}")

    part = resp.json()["candidates"][0]["content"]["parts"][0]
    return base64.b64decode(part["inlineData"]["data"])
