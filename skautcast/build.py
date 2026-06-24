"""Synthesize audio for every summary, then rebuild the feed.

For each data/summaries/<hash>.md, render it with the configured TTS backend
(config.TTS_BACKEND: "gemini" / "elevenlabs" / "xtts") -> docs/audio/<hash>.mp3
-> update state -> regenerate docs/feed.xml. An episode is re-rendered whenever
its summary text changes (tracked by a content hash), so editing a summary and
re-running build refreshes just that episode.

Usage:  python -m skautcast.build
"""
import hashlib
import re

from . import audio, config, feed, state

_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def parse_summary(path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8").strip()
    lines = raw.splitlines()
    title = path.stem
    start = 0
    if lines and lines[0].lstrip().startswith("#"):
        title = lines[0].lstrip("#").strip()
        start = 1
    body = "\n".join(lines[start:]).strip()
    return title, body


def clean_for_tts(text: str) -> str:
    text = _MD_LINK.sub(r"\1", text)            # [label](url) -> label
    text = re.sub(r"^\s*[#>*\-]+\s*", "", text, flags=re.M)  # bullet/heading marks
    text = re.sub(r"[*_`]+", "", text)          # stray emphasis marks
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _summary_sha(path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def _synthesize(spoken: str, mp3_path, wav_path) -> None:
    """Render `spoken` to mp3_path using the configured backend."""
    backend = getattr(config, "TTS_BACKEND", "gemini")
    if backend == "elevenlabs":
        from . import elevenlabs
        elevenlabs.synth_mp3(spoken, mp3_path)
    elif backend == "gemini":
        from . import gemini
        gemini.synth_wav(spoken, wav_path)
        audio.to_mp3(wav_path, mp3_path)
    else:  # local XTTS fallback
        from . import tts
        tts.synth(spoken, wav_path)
        audio.to_mp3(wav_path, mp3_path)


def build() -> int:
    config.ensure_dirs()
    st = state.load_state()
    wav_dir = config.DATA / "_wav"
    wav_dir.mkdir(parents=True, exist_ok=True)

    # make sure every summary has a state entry (covers hand-written episodes)
    for summ in config.SUMMARIES.glob("*.md"):
        st["episodes"].setdefault(summ.stem, {
            "first_seen": state.now_iso(), "status": "summarized", "url": None,
        })

    todo = []
    for h, ep in st["episodes"].items():
        summ = config.SUMMARIES / f"{h}.md"
        if not summ.exists():
            continue
        mp3 = config.AUDIO / f"{h}.mp3"
        sha = _summary_sha(summ)
        # skip only if audio exists AND the summary hasn't changed since
        if ep.get("audio_path") and mp3.exists() and ep.get("summary_sha") == sha:
            continue
        todo.append((h, ep, summ, sha))

    if not todo:
        print("[build] nothing to synthesize (all summaries up to date).")
    for i, (h, ep, summ, sha) in enumerate(todo, 1):
        title, body = parse_summary(summ)
        spoken = clean_for_tts(f"{title}. {body}")
        print(f"[build] ({i}/{len(todo)}) synthesizing: {title}", flush=True)

        mp3 = config.AUDIO / f"{h}.mp3"
        _synthesize(spoken, mp3, wav_dir / f"{h}.wav")
        dur, size = audio.probe(mp3)

        ep.update(
            title=title,
            summary_text=body,
            summary_sha=sha,
            summary_path=str(summ.relative_to(config.ROOT)),
            audio_path=f"audio/{h}.mp3",
            audio_bytes=size,
            duration_sec=dur,
            status="published",
            published_at=state.now_iso(),
        )
        state.save_state(st)  # save after each, so a crash mid-batch keeps progress
        print(f"        -> audio/{h}.mp3  ({dur}s, {size // 1024} KB)")

    feed.build_feed()
    return len(todo)


if __name__ == "__main__":
    raise SystemExit(0 if build() >= 0 else 1)
