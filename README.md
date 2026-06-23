# SkautCast

Turn the skaut HQ newsletter ("Balíček ústředí") into a private Czech podcast you
listen to in **AntennaPod**. Articles are summarized (by Claude Code), read aloud
with **XTTS-v2** (Czech), packaged as an RSS feed, and published to GitHub Pages.

It is run **manually**: you ask Claude Code to *"process the latest skaut newsletter"*
and it does the whole loop. History (`data/state.json`) means no article is ever redone.

## Pipeline

```
Gmail (read by Claude via MCP)  ->  data/inbox/<msgid>.html
  python -m skautcast.fetch <html>     # links -> resolve -> extract -> articles/*.json
  (Claude writes Czech summaries)      # data/summaries/<hash>.md
  python -m skautcast.build            # XTTS -> mp3 -> docs/feed.xml + state.json
  python -m skautcast.publish          # git push docs/ -> GitHub Pages
AntennaPod (subscribed once)  ->  auto-download + notification
```

## One-time setup

1. **Python env** (Python 3.14 is fine here):
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   # GPU (this machine has an RTX 4070):
   pip install torch --index-url https://download.pytorch.org/whl/cu126
   pip install -r requirements.txt
   ```
2. **GitHub Pages:** create a repo (use a non-obvious name — Pages sites are public),
   push this folder, then Settings -> Pages -> Source = `main` branch, `/docs` folder.
   Put the resulting `https://<user>.github.io/<repo>` into `skautcast/config.py`
   (`BASE_URL`) or the `SKAUTCAST_BASE_URL` env var.
3. **First build** downloads the XTTS model (~1.8 GB) — slow once.
4. **AntennaPod:** Add Podcast -> by URL -> `https://<user>.github.io/<repo>/feed.xml`.

## Voice

Starts with a built-in XTTS speaker (`config.TTS_SPEAKER`). List voices with
`python -m skautcast.tts --speakers`. For the most natural Czech, drop a 6-20s clean
WAV at `voices/reference.wav` and set `REFERENCE_WAV` in `config.py`.

## Useful commands

| Command | What it does |
| --- | --- |
| `python -m skautcast.tts` | Czech voice smoke test -> `data/tts_smoketest.wav` |
| `python -m skautcast.tts --speakers` | List built-in voices |
| `python -m skautcast.fetch data/inbox/X.html` | Extract new articles |
| `python -m skautcast.build` | Synthesize audio + rebuild feed |
| `python -m skautcast.publish` | Push `docs/` to GitHub Pages |
