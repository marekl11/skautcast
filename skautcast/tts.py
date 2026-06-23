"""XTTS-v2 text-to-speech wrapper (Czech).

The model is loaded once and reused. Uses the GPU automatically when available,
otherwise the CPU. The Coqui model license is accepted non-interactively via the
COQUI_TOS_AGREED env var so the first run can download the model unattended.
"""
import os

os.environ.setdefault("COQUI_TOS_AGREED", "1")

from pathlib import Path

from . import config

_tts = None
_device = None


def get_tts():
    """Lazy-load and cache the XTTS-v2 model."""
    global _tts, _device
    if _tts is None:
        import torch
        from TTS.api import TTS

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[tts] loading {config.TTS_MODEL} on {_device} ...", flush=True)
        _tts = TTS(config.TTS_MODEL).to(_device)
    return _tts


def list_speakers() -> list[str]:
    tts = get_tts()
    try:
        names = list(tts.speakers or [])
        if names:
            return names
    except Exception:
        pass
    try:
        sm = tts.synthesizer.tts_model.speaker_manager
        return list(sm.name_to_id.keys())
    except Exception:
        return []


def synth(text: str, out_wav: Path, speaker: str | None = None,
          reference_wav: Path | None = None) -> Path:
    tts = get_tts()
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    kwargs = dict(
        text=text,
        file_path=str(out_wav),
        language=config.TTS_LANGUAGE,
        split_sentences=True,
    )
    ref = reference_wav or config.REFERENCE_WAV
    if ref:
        kwargs["speaker_wav"] = str(ref)
    else:
        kwargs["speaker"] = speaker or config.TTS_SPEAKER

    tts.tts_to_file(**kwargs)
    return out_wav


def _main(argv: list[str]) -> int:
    if "--speakers" in argv:
        for name in list_speakers():
            print(name)
        return 0

    # parse optional --speaker NAME
    speaker = None
    if "--speaker" in argv:
        i = argv.index("--speaker")
        speaker = argv[i + 1]
        del argv[i:i + 2]

    text = argv[0] if argv else (
        "Ahoj, tady SkautCast. Toto je zkušební nahrávka českého hlasu. "
        "Devětadvacátého června začíná letní tábor."
    )
    out = Path(argv[1]) if len(argv) > 1 else (config.DATA / "tts_smoketest.wav")
    synth(text, out, speaker=speaker)
    print(f"[tts] wrote {out}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
