"""XTTS-v2 text-to-speech wrapper (Czech).

The model is loaded once and reused. Uses the GPU automatically when available,
otherwise the CPU. The Coqui model license is accepted non-interactively via the
COQUI_TOS_AGREED env var so the first run can download the model unattended.
"""
import os

os.environ.setdefault("COQUI_TOS_AGREED", "1")

import re
from pathlib import Path

from . import config

_tts = None
_device = None

# XTTS truncates audio for sentences longer than this many characters (Czech).
_CS_CHAR_LIMIT = 180
_SENT_SPLIT = re.compile(r"(?<=[.!?:;])\s+")


def _limit_sentence_len(text: str, limit: int = _CS_CHAR_LIMIT) -> str:
    """Break any sentence longer than the XTTS limit at commas, so nothing gets
    truncated. A comma pause simply becomes a sentence pause."""
    out: list[str] = []
    for sent in _SENT_SPLIT.split(text):
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) <= limit:
            out.append(sent)
            continue
        buf = ""
        for part in sent.split(","):
            part = part.strip()
            if not part:
                continue
            cand = f"{buf}, {part}" if buf else part
            if len(cand) <= limit:
                buf = cand
            else:
                if buf:
                    out.append(buf)
                buf = part
        if buf:
            out.append(buf)

    def _term(s: str) -> str:
        # XTTS only splits on . ! ? — force every piece to end with one,
        # otherwise pieces ending in : ; , get re-merged past the limit.
        s = s.rstrip()
        while s and s[-1] in ",;:":
            s = s[:-1].rstrip()
        if s and s[-1] not in ".!?":
            s += "."
        return s

    return " ".join(_term(s) for s in out if _term(s))


def _patch_czech_ordinals() -> None:
    """XTTS's Czech tokenizer expands any 'number.' as an ordinal via num2words,
    but num2words has no Czech ordinals and raises NotImplementedError (crashing
    on almost any text with a year/date). Fall back to the cardinal form, which
    is also how Czech normally reads years aloud."""
    try:
        from num2words.lang_CS import Num2Word_CS
        if getattr(Num2Word_CS, "_skautcast_patched", False):
            return
        Num2Word_CS.to_ordinal = lambda self, number: self.to_cardinal(number)
        Num2Word_CS.to_ordinal_num = lambda self, number: self.to_cardinal(number)
        Num2Word_CS._skautcast_patched = True
    except Exception:
        pass


def _patch_audio_loader() -> None:
    """coqui-tts loads speaker_wav via torchaudio.load, which on torch 2.11+
    dispatches to torchcodec and needs FFmpeg shared libraries we don't have.
    Load reference audio with soundfile instead (libsndfile, no FFmpeg).
    torchaudio.functional.resample is pure tensor math, so it stays."""
    try:
        import TTS.tts.models.xtts as _xtts
        if getattr(_xtts, "_skautcast_audio_patched", False):
            return
        import soundfile as sf
        import torch as _torch
        import torchaudio

        def _load_audio(audiopath, sampling_rate):
            if isinstance(audiopath, (list, tuple)):
                audiopath = audiopath[0]
            data, lsr = sf.read(str(audiopath), dtype="float32", always_2d=True)
            audio = _torch.from_numpy(data.T)  # (channels, samples)
            if audio.size(0) != 1:
                audio = _torch.mean(audio, dim=0, keepdim=True)
            if lsr != sampling_rate:
                audio = torchaudio.functional.resample(audio, lsr, sampling_rate)
            return audio.clip(-1.0, 1.0)

        _xtts.load_audio = _load_audio
        _xtts._skautcast_audio_patched = True
    except Exception as exc:
        print(f"[tts] audio loader patch skipped: {exc}")


def get_tts():
    """Lazy-load and cache the XTTS-v2 model."""
    global _tts, _device
    if _tts is None:
        import torch
        from TTS.api import TTS

        _patch_czech_ordinals()
        _patch_audio_loader()
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
    import numpy as np
    import soundfile as sf

    tts = get_tts()
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    text = _limit_sentence_len(text)
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()] or [text]

    infer = dict(getattr(config, "TTS_INFERENCE", {}))
    common = dict(language=config.TTS_LANGUAGE, split_sentences=False)
    ref = reference_wav or config.REFERENCE_WAV
    if ref:
        common["speaker_wav"] = str(ref)
    else:
        common["speaker"] = speaker or config.TTS_SPEAKER
        for k in ("gpt_cond_len", "gpt_cond_chunk_len", "max_ref_len", "sound_norm_refs"):
            infer.pop(k, None)
    common.update(infer)

    sr = getattr(getattr(tts, "synthesizer", None), "output_sample_rate", 24000) or 24000
    gap = np.zeros(int(sr * getattr(config, "SENTENCE_GAP_MS", 160) / 1000), dtype=np.float32)
    fade_n = max(1, int(sr * getattr(config, "EDGE_FADE_MS", 12) / 1000))
    ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)

    # Synthesize each sentence separately; fade edges to zero so the joins
    # can't click, then stitch with a short silence gap between sentences.
    import librosa
    top_db = getattr(config, "TRIM_TOP_DB", 28)
    pieces = []
    for sent in sentences:
        wav = np.asarray(tts.tts(text=sent, **common), dtype=np.float32)
        wav, _ = librosa.effects.trim(wav, top_db=top_db)  # drop chunk's own padding
        if wav.size > 2 * fade_n:
            wav[:fade_n] *= ramp
            wav[-fade_n:] *= ramp[::-1]
        pieces.append(wav)
        pieces.append(gap)
    audio = np.concatenate(pieces[:-1]) if len(pieces) > 1 else pieces[0]
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = (audio / peak * 0.97).astype(np.float32)  # gentle peak normalize
    sf.write(str(out_wav), audio, sr)
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
