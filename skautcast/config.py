"""Central configuration for SkautCast.

Edit the values in this file to your liking. The two you are most likely to
change are BASE_URL (your GitHub Pages address) and the TTS voice settings.
Most values can also be overridden with environment variables.
"""
import os
from pathlib import Path

# --- Paths ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INBOX = DATA / "inbox"            # saved newsletter HTML (gitignored)
ARTICLES = DATA / "articles"     # extracted article text + metadata (gitignored)
SUMMARIES = DATA / "summaries"   # Claude-written summaries (the script reads these)
STATE_FILE = DATA / "state.json"  # history / "what's already done"
PENDING_FILE = DATA / "pending.json"  # list of hashes awaiting a summary

DOCS = ROOT / "docs"             # GitHub Pages publish root
AUDIO = DOCS / "audio"           # published mp3 episodes
FEED_FILE = DOCS / "feed.xml"
COVER_FILE = DOCS / "cover.png"
VOICES = ROOT / "voices"         # optional reference.wav for voice cloning


def ensure_dirs() -> None:
    for d in (INBOX, ARTICLES, SUMMARIES, AUDIO, VOICES):
        d.mkdir(parents=True, exist_ok=True)


# --- Feed metadata ----------------------------------------------------------
# IMPORTANT: set this to your GitHub Pages URL (no trailing slash), e.g.
#   https://<your-user>.github.io/<your-repo>
# You can also override it without editing this file:  set SKAUTCAST_BASE_URL=...
BASE_URL = os.environ.get(
    "SKAUTCAST_BASE_URL", "https://EXAMPLE.github.io/skautcast"
).rstrip("/")

FEED_TITLE = "SkautCast"
FEED_AUTHOR = "SkautCast"
FEED_EMAIL = os.environ.get("SKAUTCAST_EMAIL", "mareksakul@gmail.com")
FEED_DESCRIPTION = "Skautské novinky z Balíčku ústředí, předčítané nahlas."
FEED_LANGUAGE = "cs"
FEED_CATEGORY = "Society & Culture"

# --- TTS (XTTS-v2) ----------------------------------------------------------
TTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
TTS_LANGUAGE = "cs"
# Built-in XTTS speaker name. List them with:  python -m skautcast.tts --speakers
TTS_SPEAKER = os.environ.get("SKAUTCAST_SPEAKER", "Daisy Studious")
# To clone a voice instead, point this at a 6-20s clean WAV and it takes priority.
REFERENCE_WAV = None  # e.g. VOICES / "reference.wav"

# --- Audio output -----------------------------------------------------------
MP3_BITRATE = "64k"
MP3_SAMPLE_RATE = 24000  # XTTS outputs 24 kHz
MP3_CHANNELS = 1         # mono is plenty for speech

# --- Link filtering ---------------------------------------------------------
# A link counts as an article only if its FINAL (post-redirect) host ends with
# one of these and it is not blocked below.
ALLOW_HOST_SUFFIXES = ("skaut.cz",)
BLOCK_HOST_SUFFIXES = (
    "storage.googleapis.com", "fonts.googleapis.com", "google.com",
    "facebook.com", "instagram.com", "youtube.com", "youtu.be",
    "whatsapp.com", "twitter.com", "x.com", "sparkpostmail.com",
    "apps.apple.com", "play.google.com",
)
BLOCK_PATH_SUBSTR = (
    "odhlasit", "unsubscribe", "logout", "odhlaseni",
)

# Below this many characters, treat the article fetch as failed (e.g. a login
# wall) and fall back to the newsletter's own blurb text for that link.
MIN_ARTICLE_CHARS = 350

# Network politeness
HTTP_TIMEOUT = 20
HTTP_DELAY = 1.0  # seconds between requests
USER_AGENT = "Mozilla/5.0 (SkautCast personal podcast generator)"
