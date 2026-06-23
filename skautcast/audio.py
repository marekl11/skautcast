"""WAV -> MP3 conversion and probing, using the ffmpeg binary bundled with
imageio-ffmpeg (so no system ffmpeg install / PATH setup is needed)."""
import subprocess
from pathlib import Path

import imageio_ffmpeg
from mutagen.mp3 import MP3

from . import config


def to_mp3(wav_path: Path, mp3_path: Path) -> Path:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            ff, "-y", "-loglevel", "error",
            "-i", str(wav_path),
            "-ac", str(config.MP3_CHANNELS),
            "-ar", str(config.MP3_SAMPLE_RATE),
            "-b:a", config.MP3_BITRATE,
            str(mp3_path),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr}")
    return mp3_path


def probe(mp3_path: Path) -> tuple[int, int]:
    """Return (duration_seconds, byte_size) for a finished mp3."""
    audio = MP3(str(mp3_path))
    return int(round(audio.info.length)), mp3_path.stat().st_size
