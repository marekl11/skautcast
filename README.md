# SkautCast

Turn the skaut HQ newsletter ("Balíček ústředí") into a private Czech podcast you
listen to in **AntennaPod**. Each article is summarized (by Claude Code, following
[SUMMARY_STYLE.md](SUMMARY_STYLE.md)), read aloud by a TTS voice, packaged as an RSS
feed with per-episode artwork and source links, and published to GitHub Pages.

Run **manually**: you ask Claude Code to *"process the latest skaut newsletter"* and it
does the whole loop. History (`data/state.json`) means no article is ever redone, and an
episode is re-rendered only when its summary changes.

## Pipeline

```
Gmail (read by Claude via MCP)  ->  data/inbox/<msgid>.html
  python -m skautcast.fetch <html>     # links -> resolve -> extract text + og:image -> articles/*.json
  (Claude writes Czech summaries)      # data/summaries/<hash>.md  (see SUMMARY_STYLE.md)
  python -m skautcast.build            # TTS -> docs/audio/*.mp3 + docs/img/*.jpg + feed.xml + state.json
  python -m skautcast.publish          # git push docs/ -> GitHub Pages
AntennaPod (subscribed once)  ->  auto-download + notification
```

## Voice / TTS backends

Set `TTS_BACKEND` in [skautcast/config.py](skautcast/config.py):

| Backend | Quality | Cost | Notes |
| --- | --- | --- | --- |
| **`gemini`** (default) | studio, native Czech | free tier | Google AI Studio key in `.gemini_key`. Voice + style are promptable (`GEMINI_VOICE`, `GEMINI_STYLE`); currently **Charon**, calm/educational. |
| `elevenlabs` | studio | paid for cloned voices | key in `.elevenlabs_key`, `ELEVENLABS_VOICE_ID`. Free tier blocks library/cloned voices. |
| `xtts` | good (local) | free / offline | Local XTTS-v2 + optional voice cloning (`voices/reference.wav`). Needs the optional PyTorch deps. |

Keys live in gitignored files (`.gemini_key`, `.elevenlabs_key`) or env vars.

## One-time setup

1. **Python env:** `py -m venv .venv` → activate → `pip install -r requirements.txt`.
2. **TTS key:** for Gemini, get a free key at **aistudio.google.com** → save it to `.gemini_key`.
3. **GitHub Pages:** already wired to `https://marekl11.github.io/skautcast` (Settings →
   Pages → `main` / `/docs`). Change `BASE_URL` in config if the repo changes.
4. **AntennaPod:** Add Podcast → by URL → `https://marekl11.github.io/skautcast/feed.xml`.

## Commands

| Command | What it does |
| --- | --- |
| `python -m skautcast.fetch data/inbox/X.html` | Resolve links, extract new articles + images |
| `python -m skautcast.build` | Render audio for new/changed summaries + rebuild feed |
| `python -m skautcast.publish` | Push `docs/` to GitHub Pages |

## Layout

```
skautcast/   config, state, fetch, build, feed, audio
             gemini.py / elevenlabs.py / tts.py   (TTS backends)
data/        inbox/ articles/ summaries/ state.json   (working data + history)
docs/        feed.xml, cover.png, audio/*.mp3, img/*.jpg   (published to Pages)
SUMMARY_STYLE.md   how episode summaries are written
```
