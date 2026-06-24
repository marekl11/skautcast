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
    "SKAUTCAST_BASE_URL", "https://marekl11.github.io/skautcast"
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
REFERENCE_WAV = VOICES / "reference.wav"  # cloned "Kuba" voice; takes priority over TTS_SPEAKER

# XTTS inference tuning. Lower temperature + higher repetition_penalty = fewer
# glitches/stutters (at the cost of slightly flatter prosody). gpt_cond_len is
# how many seconds of the reference are used for voice conditioning (~30s cap).
TTS_INFERENCE = {
    "temperature": 0.6,
    "length_penalty": 1.0,
    "repetition_penalty": 5.0,
    "top_k": 50,
    "top_p": 0.8,
    "speed": 1.0,
    "gpt_cond_len": 40,
    "gpt_cond_chunk_len": 6,
    "max_ref_len": 40,
    "sound_norm_refs": True,
}

# Per-sentence stitching to kill XTTS boundary clicks: synthesize each sentence
# on its own, fade its edges to zero (so joins can't pop), and stitch with a gap.
SENTENCE_GAP_MS = 90    # silence between sentences (after trimming each chunk's own padding)
EDGE_FADE_MS = 12       # fade-in/out length applied to each sentence chunk
TRIM_TOP_DB = 28        # trim silence quieter than this below peak from each chunk

# --- TTS backend -----------------------------------------------------------
# "gemini" (Google AI Studio, free, Czech), "elevenlabs" (studio, paid for
# cloned voices), or "xtts" (local, free/offline)
TTS_BACKEND = os.environ.get("SKAUTCAST_TTS_BACKEND", "gemini")


def _read_secret(env_name: str, filename: str):
    val = os.environ.get(env_name)
    if val:
        return val.strip()
    p = ROOT / filename
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


# ElevenLabs (used when TTS_BACKEND == "elevenlabs"). The API key is read from
# the ELEVENLABS_API_KEY env var or a gitignored .elevenlabs_key file.
ELEVENLABS_API_KEY = _read_secret("ELEVENLABS_API_KEY", ".elevenlabs_key")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "Lr0h58bpmHY6zGpS4Hef")  # Kuba voice
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}

# Gemini TTS (used when TTS_BACKEND == "gemini"). Free key from aistudio.google.com,
# read from GEMINI_API_KEY env var or a gitignored .gemini_key file.
GEMINI_API_KEY = _read_secret("GEMINI_API_KEY", ".gemini_key")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_VOICE = os.environ.get("GEMINI_VOICE", "Charon")  # calm/informative
# Style directive (Czech) — the model follows it but reads only the text after it.
GEMINI_STYLE = (
    "Čti následující text jako zkušený moderátor populárně naučného podcastu. "
    "Mluv srozumitelně, klidně a přátelsky, ale živě a s přirozenou, výraznou "
    "intonací. Zdůrazňuj klíčová slova, přirozeně měň tempo i melodii hlasu a "
    "dělej krátké pomlky mezi myšlenkami, ať se text dobře poslouchá a snadno "
    "chápe. Vyhni se monotónnímu a strojovému projevu. "
    "Čti pouze samotný text, nic nepřidávej:")

# --- Audio output -----------------------------------------------------------
MP3_BITRATE = "64k"
MP3_SAMPLE_RATE = 24000  # XTTS outputs 24 kHz
MP3_CHANNELS = 1         # mono is plenty for speech

# ffmpeg audio post-processing applied during wav -> mp3 (set "" to disable):
#   adeclick  - removes pops/clicks (the main XTTS artifact)
#   loudnorm  - consistent podcast loudness (~-16 LUFS)
AUDIO_FILTER = "adeclick,loudnorm=I=-16:TP=-1.5:LRA=11"

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
