# SkautCast

Turn the skaut HQ newsletter ("Balíček ústředí") into a Czech podcast, *Skautské
minutky*, listened to on **Spotify** and in the Podcast tab of **Skautban** (the scout
board app). Each article is summarized (by Claude Code, following
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
Spotify (show added once from the feed)  ->  picks up new episodes by itself, within hours
Skautban (Podcast tab)                   ->  reads feed.xml in the browser, new episodes at once
```

## Voice / TTS

TTS is **Gemini** (Google AI Studio) — studio quality, native Czech, free tier, and the
speaking style is promptable. Configured in [skautcast/config.py](skautcast/config.py):
the voice alternates per episode between **Charon** (male) and **Callirrhoe** (female) —
each episode picks one deterministically from its hash, so the feed mixes voices but a
given episode never flips — and the delivery is shaped by `GEMINI_STYLE`. The key lives in
a gitignored `.gemini_key` file (or the `GEMINI_API_KEY` env var).

To give one episode a particular voice (say, the two halves of a series read by a man and
a woman when their hashes happen to pick the same voice), set its `voice_override` in
`data/state.json` to one of `GEMINI_VOICES`.

Text longer than `GEMINI_MAX_CHARS` (3200, about three and a half minutes of speech) is
read in several requests, split at paragraph breaks and joined with a short pause
(`GEMINI_PART_GAP_MS`). Ordinary episodes fit in one request; this is for the occasional
ten-minute one, where a single long request risks the voice drifting or being cut short.

### Intro (AI notice + jingle)

Every episode starts with a short spoken **"Napsala a namluvila umělá inteligence."**
notice, then the intro jingle, then the summary: **notice → jingle → speech**. The notice is
generated once per voice, sped up (`DISCLAIMER_TEMPO`) and loudness-matched, and cached at
`assets/disclaimer_<voice>.wav`; the jingle lives at `assets/jingle.wav`. Delete a cached
notice to regenerate it after changing the config.

The wording is deliberately terse — the intro runs before every episode and episodes are
only ~2 minutes, so it earns its seconds. Note that most of the intro is the jingle (2.9 s),
not the notice (~3.0 s): raising `DISCLAIMER_TEMPO` buys very little, so shorten the wording
instead if it ever needs to be tighter.

### AI Act disclosure

The disclosure has **two halves, and both are required** — don't drop one while tidying up:

- **Spoken** (`DISCLAIMER_TEXT`) — the audible disclaimer at the start of every episode.
- **Written** (`AI_DISCLOSURE_LINE`) — the first paragraph of every episode's show notes,
  plus a sentence in `FEED_DESCRIPTION`. The Code of Practice on Transparency of
  AI-generated Content asks for a visual label *in addition to* the audible one wherever a
  screen is available, and the show-notes text is itself AI-written.

Both mention the *text* as well as the voice, because episodes publish with no human
editorial review — which is what would otherwise exempt AI-generated text under Article
50(4) of the AI Act. If a human ever starts reviewing episodes before publication, that
part of the wording can be revisited.

### Show notes

Emitted as a small HTML document (`feed._episode_description`): AI disclosure, a link
to the source article, then the episode's blurb. Extra hand-picked links (say, a Facebook
post about the article) go in the episode's `extra_links` list in `data/state.json` as
`{"text", "url"}` and show up under the article link. Podcast clients render a limited HTML
subset, which is what gives the paragraphs their spacing and makes the link clickable —
a bare URL in plain text shows up as dead characters in most apps.

The blurb comes from the `> ` block under the title in the summary file, never from the
transcript. Because the content hash covers only the *spoken* text, rewriting a blurb
refreshes the show notes without re-synthesizing any audio.

### Episode images

Each episode's image is its article's `og:image`, saved as `docs/img/<hash>.jpg` no
bigger than `IMAGE_MAX_PX` (1280 px) on the long side. Article photos often come
straight off a camera, up to 24 MB, while players and the Skautban grid show them a few
hundred pixels wide. An image kept from before (larger, or a PNG) is shrunk on the next
build.

## One-time setup

1. **Python env:** `py -m venv .venv` → activate → `pip install -r requirements.txt`.
2. **TTS key:** for Gemini, get a free key at **aistudio.google.com** → save it to `.gemini_key`.
3. **GitHub Pages:** already wired to `https://marekl11.github.io/skautcast` (Settings →
   Pages → `main` / `/docs`). Change `BASE_URL` in config if the repo changes.
4. **Listeners:** the show is on Spotify
   (`https://open.spotify.com/show/0343NuteYi6unrnhj43d5S`), added once from
   `https://marekl11.github.io/skautcast/feed.xml`, which Spotify re-reads on its own.
   Skautban reads the same feed (`FEED_URL` in its `src/lib/podcast.ts`), so there is
   nothing to set up on either side when publishing.

## Commands

| Command | What it does |
| --- | --- |
| `python -m skautcast.fetch data/inbox/X.html` | Resolve links, extract new articles + images |
| `python -m skautcast.build` | Render audio for new/changed summaries + rebuild feed |
| `python -m skautcast.build --force` | Re-render every episode (e.g. after an audio-pipeline change) |
| `python -m skautcast.publish` | Push `docs/` to GitHub Pages |

## Layout

```
skautcast/   config, state, fetch, build, feed, audio, gemini (TTS), publish
assets/      jingle.wav + generated disclaimer_<voice>.wav   (intro audio)
data/        inbox/ articles/ summaries/ state.json   (working data + history)
docs/        feed.xml, cover.png, audio/*.mp3, img/*.jpg   (published to Pages)
SUMMARY_STYLE.md   how episode summaries are written
```
