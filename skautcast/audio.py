"""ffmpeg audio operations: encode speech WAV -> MP3 (optionally prepending intro
clips), probe a finished mp3, and generate the cached per-voice AI-notice clip.

Uses the ffmpeg binary bundled with imageio-ffmpeg, so no system ffmpeg install /
PATH setup is needed."""
import os
import subprocess
from pathlib import Path

import imageio_ffmpeg
from mutagen.mp3 import MP3

from . import config

# All concat segments are forced to this common format so the ffmpeg concat filter
# (which does not resample) always sees matching streams.
_AFORMAT = "aformat=sample_fmts=s16:sample_rates=24000:channel_layouts=mono"


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()}")


def to_mp3(wav_path, mp3_path, intro_clips=()) -> Path:
    """Encode `wav_path` (the speech) to `mp3_path`, optionally prepending intros.

    intro_clips is an ordered sequence of (clip_path, gap_ms). Each clip is kept at
    its own baked-in loudness and followed by `gap_ms` of silence; missing clips are
    skipped. Only the speech gets AUDIO_FILTER (adeclick+loudnorm), so the intros
    keep their pre-normalized level and the speech is normalized independently.
    """
    ff = _ffmpeg()
    wav_path, mp3_path = Path(wav_path), Path(mp3_path)
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    audio_filter = getattr(config, "AUDIO_FILTER", "")

    intros = [(Path(p), gap) for p, gap in intro_clips if p and Path(p).exists()]

    if not intros:
        cmd = [ff, "-y", "-loglevel", "error", "-i", str(wav_path)]
        if audio_filter:
            cmd += ["-af", audio_filter]
    else:
        inputs: list[str] = []
        for clip, _ in intros:
            inputs += ["-i", str(clip)]
        inputs += ["-i", str(wav_path)]  # speech is the last input

        parts, labels = [], []
        for i, (_, gap) in enumerate(intros):
            parts.append(f"[{i}:a]apad=pad_dur={gap / 1000.0},{_AFORMAT}[a{i}]")
            labels.append(f"[a{i}]")
        s = len(intros)  # speech input index
        speech = f"{audio_filter}," if audio_filter else ""
        parts.append(f"[{s}:a]{speech}{_AFORMAT}[s]")
        labels.append("[s]")
        filtergraph = (";".join(parts) +
                       f";{''.join(labels)}concat=n={s + 1}:v=0:a=1[out]")
        cmd = [ff, "-y", "-loglevel", "error", *inputs,
               "-filter_complex", filtergraph, "-map", "[out]"]

    cmd += [
        "-ac", str(config.MP3_CHANNELS),
        "-ar", str(config.MP3_SAMPLE_RATE),
        "-b:a", config.MP3_BITRATE,
        str(mp3_path),
    ]
    _run(cmd)
    return mp3_path


def ensure_disclaimer(voice: str) -> Path:
    """Return the cached AI-notice clip for `voice`, generating it once if missing.

    The notice is synthesized with Gemini (read plainly), sped up (DISCLAIMER_TEMPO)
    and loudness-matched to the voice (-16 LUFS), with short fades so it concatenates
    cleanly. Delete the cached file to regenerate after changing the config."""
    out = config.disclaimer_path(voice)
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)

    from . import gemini
    raw = out.with_name(out.stem + ".raw.wav")   # Gemini PCM before processing
    tmp = out.with_name(out.stem + ".tmp.wav")   # ffmpeg output before publishing
    tempo = getattr(config, "DISCLAIMER_TEMPO", 1.15)
    chain = (f"atempo={tempo},loudnorm=I=-16:TP=-1.5:LRA=11,"
             f"afade=t=in:d=0.02,areverse,afade=t=in:d=0.02,areverse,{_AFORMAT}")
    try:
        gemini.synth_wav(config.DISCLAIMER_TEXT, raw, voice=voice,
                         style=getattr(config, "DISCLAIMER_STYLE", ""))
        _run([_ffmpeg(), "-y", "-loglevel", "error",
              "-i", str(raw), "-af", chain, str(tmp)])
        os.replace(tmp, out)  # publish only a fully-rendered file (atomic)
    finally:
        raw.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
    return out


def probe(mp3_path) -> tuple[int, int]:
    """Return (duration_seconds, byte_size) for a finished mp3."""
    mp3_path = Path(mp3_path)
    return int(round(MP3(str(mp3_path)).info.length)), mp3_path.stat().st_size
