"""Synthesize audio for every summary that doesn't have it yet, then rebuild
the feed.

For each data/summaries/<hash>.md that lacks a published mp3:
  parse title + body -> XTTS (cs) -> wav -> mp3 -> probe -> update state.
Finally regenerate docs/feed.xml from the full history.

Usage:  python -m skautcast.build
"""
import re
import sys

from . import audio, config, feed, state, tts

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


def build() -> int:
    config.ensure_dirs()
    st = state.load_state()
    wav_dir = config.DATA / "_wav"
    wav_dir.mkdir(parents=True, exist_ok=True)

    # make sure every summary has a state entry (covers hand-written v0 episodes)
    for summ in config.SUMMARIES.glob("*.md"):
        st["episodes"].setdefault(summ.stem, {
            "first_seen": state.now_iso(), "status": "summarized", "url": None,
        })

    todo = []
    for h, ep in st["episodes"].items():
        summ = config.SUMMARIES / f"{h}.md"
        mp3 = config.AUDIO / f"{h}.mp3"
        if summ.exists() and not (ep.get("audio_path") and mp3.exists()):
            todo.append((h, ep, summ))

    if not todo:
        print("[build] no new summaries to synthesize.")
    for i, (h, ep, summ) in enumerate(todo, 1):
        title, body = parse_summary(summ)
        spoken = clean_for_tts(f"{title}. {body}")
        print(f"[build] ({i}/{len(todo)}) synthesizing: {title}")

        wav = wav_dir / f"{h}.wav"
        tts.synth(spoken, wav)
        mp3 = config.AUDIO / f"{h}.mp3"
        audio.to_mp3(wav, mp3)
        dur, size = audio.probe(mp3)

        ep.update(
            title=title,
            summary_text=body,
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
