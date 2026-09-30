"""Synthesize audio for every summary, then rebuild the feed.

For each data/summaries/<hash>.md, render it with Gemini TTS -> docs/audio/<hash>.mp3,
update state, and regenerate docs/feed.xml. Each episode gets an AI-narration notice
and the intro jingle prepended (notice -> jingle -> speech). An episode is re-rendered
whenever its summary text changes (tracked by a content hash); pass --force to
re-render everything (e.g. after changing the audio pipeline).

Usage:  python -m skautcast.build [--force]
"""
import hashlib
import re
import sys

from . import audio, config, feed, gemini, state

_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def parse_summary(raw: str, default_title: str) -> tuple[str, str, str]:
    """Split a summary file into (title, blurb, body).

    The blurb is an optional `> ...` block directly under the title. It goes into the
    show notes only and is never spoken, so rewriting it does not change the audio.
    """
    lines = raw.strip().splitlines()
    title, start = default_title, 0
    if lines and lines[0].lstrip().startswith("#"):
        title = lines[0].lstrip("#").strip()
        start = 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    blurb = []
    while start < len(lines) and lines[start].lstrip().startswith(">"):
        blurb.append(lines[start].lstrip().lstrip(">").strip())
        start += 1
    return title, " ".join(blurb).strip(), "\n".join(lines[start:]).strip()


def clean_for_tts(text: str) -> str:
    text = _MD_LINK.sub(r"\1", text)            # [label](url) -> label
    text = re.sub(r"^\s*[#>*\-]+\s*", "", text, flags=re.M)  # bullet/heading marks
    text = re.sub(r"[*_`]+", "", text)          # stray emphasis marks
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _voice_for(h: str) -> str:
    """Deterministically pick a Gemini voice from the pool based on the episode
    hash, so the feed alternates male/female but a given episode is stable across
    re-renders. Falls back to the single default voice if no pool is configured."""
    pool = getattr(config, "GEMINI_VOICES", None) or [config.GEMINI_VOICE]
    try:
        idx = int(h[:8], 16) % len(pool)
    except ValueError:
        idx = 0
    return pool[idx]


def _render(spoken: str, mp3_path, wav_path, voice: str) -> None:
    """Synthesize `spoken` with Gemini and encode to mp3, prepending the voice's
    AI-notice and the intro jingle."""
    gemini.synth_wav(spoken, wav_path, voice=voice)
    intro = [
        (audio.ensure_disclaimer(voice), config.DISCLAIMER_GAP_MS),
        (config.JINGLE_FILE, config.JINGLE_GAP_MS),
    ]
    audio.to_mp3(wav_path, mp3_path, intro_clips=intro)


def build(force: bool = False) -> int:
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
        title, blurb, body = parse_summary(summ.read_text(encoding="utf-8"), summ.stem)
        spoken = clean_for_tts(f"{title}. {body}")
        # Hash the SPOKEN text, not the file: rewriting the show-notes blurb would
        # otherwise re-synthesize audio that comes out identical.
        sha = hashlib.sha1(spoken.encode("utf-8")).hexdigest()[:12]
        mp3 = config.AUDIO / f"{h}.mp3"
        # skip only if audio exists AND the spoken text hasn't changed (unless forced)
        if not force and ep.get("audio_path") and mp3.exists() and ep.get("summary_sha") == sha:
            # still refresh the show-notes fields, which cost nothing to update
            ep.update(title=title, blurb=blurb, summary_text=body)
            continue
        todo.append((h, ep, summ, sha, title, blurb, body, spoken))
    state.save_state(st)

    if not todo:
        print("[build] nothing to synthesize (all summaries up to date).")
    for i, (h, ep, summ, sha, title, blurb, body, spoken) in enumerate(todo, 1):
        # A voice set by hand in state.json wins, e.g. so the two halves of a series
        # get a man and a woman even when their hashes pick the same voice.
        voice = ep.get("voice_override") or _voice_for(h)
        print(f"[build] ({i}/{len(todo)}) synthesizing [{voice}]: {title}", flush=True)

        mp3 = config.AUDIO / f"{h}.mp3"
        _render(spoken, mp3, wav_dir / f"{h}.wav", voice)
        dur, size = audio.probe(mp3)

        ep.update(
            title=title,
            blurb=blurb,
            summary_text=body,
            summary_sha=sha,
            summary_path=str(summ.relative_to(config.ROOT)),
            voice=voice,
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
    # Czech titles must survive a legacy-codepage Windows console.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(0 if build(force="--force" in sys.argv[1:]) >= 0 else 1)
