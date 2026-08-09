"""Central configuration for SkautCast.

Edit the values in this file to your liking. The one you are most likely to
change is BASE_URL (your GitHub Pages address). The TTS voice and speaking style
live in the Gemini section. Most values can also be overridden with env vars.
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
# jpg: the artwork has gradients PNG compresses badly. The -vN suffix is cache-busting:
# itunes:image can't carry a ?v= query (feedgen requires a .jpg/.png suffix), so bump the
# number when the artwork changes to force players to re-fetch instead of serving a cached one.
COVER_FILE = DOCS / "cover-v2.jpg"
ASSETS = ROOT / "assets"         # intro jingle + generated AI-notice clips


def ensure_dirs() -> None:
    for d in (INBOX, ARTICLES, SUMMARIES, AUDIO, ASSETS):
        d.mkdir(parents=True, exist_ok=True)


# --- Feed metadata ----------------------------------------------------------
# IMPORTANT: set this to your GitHub Pages URL (no trailing slash), e.g.
#   https://<your-user>.github.io/<your-repo>
# You can also override it without editing this file:  set SKAUTCAST_BASE_URL=...
BASE_URL = os.environ.get(
    "SKAUTCAST_BASE_URL", "https://marekl11.github.io/skautcast"
).rstrip("/")

FEED_TITLE = "Skautské minutky"
FEED_SUBTITLE = "Novinky z Křižovatky"   # itunes:subtitle — one-liner under the title
FEED_AUTHOR = "Skautské minutky"
FEED_EMAIL = os.environ.get("SKAUTCAST_EMAIL", "mareksakul@gmail.com")
# NOTE: the closing AI sentence is the written half of the AI Act disclosure and is
# not optional — see the AI notice section below and README.
FEED_DESCRIPTION = (
    "Skautské novinky z Křižovatky, namluvené a zkrácené na malé jednotky minut. "
    "Žádné prokousávání se články – projedeš názvy, vyzobeš si jen ty díly, co "
    "chceš, a zbytek s klidem přeskočíš. Ideálně třeba cestou na schůzku! "
    "Epizody píše i namlouvá umělá inteligence."
)
FEED_LANGUAGE = "cs"
FEED_CATEGORY = "Society & Culture"


def _read_secret(env_name: str, filename: str):
    val = os.environ.get(env_name)
    if val:
        return val.strip()
    p = ROOT / filename
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


# --- Gemini TTS -------------------------------------------------------------
# Google AI Studio, free tier, native Czech, promptable speaking style. Get a
# free key at aistudio.google.com and put it in GEMINI_API_KEY or a .gemini_key file.
GEMINI_API_KEY = _read_secret("GEMINI_API_KEY", ".gemini_key")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_VOICE = os.environ.get("GEMINI_VOICE", "Charon")  # calm/informative (default)
# Voices alternated per episode to keep the listener's attention. Each episode
# deterministically picks one based on its hash (stable across re-renders), so the
# feed mixes male (Charon) and female (Callirrhoe) but a given episode never flips.
GEMINI_VOICES = ["Charon", "Callirrhoe"]
# Style directive (Czech) — the model follows it but reads only the text after it.
GEMINI_STYLE = (
    "Čti následující text jako zkušený moderátor populárně naučného podcastu. "
    "Mluv srozumitelně, klidně a přátelsky, ale živě a s přirozenou, výraznou "
    "intonací. Zdůrazňuj klíčová slova, přirozeně měň tempo i melodii hlasu a "
    "dělej krátké pomlky mezi myšlenkami, ať se text dobře poslouchá a snadno "
    "chápe. Vyhni se monotónnímu a strojovému projevu. "
    "Čti pouze samotný text, nic nepřidávej:")

# --- AI notice (EU AI Act) --------------------------------------------------
# A short spoken disclosure that the episode is AI-narrated, prepended before the
# jingle. Generated once per voice and cached at assets/disclaimer_<voice>.wav
# (sped up + loudness-matched), so it matches the episode's voice and costs nothing
# to re-render. Delete the cached file(s) to regenerate after changing these.
DISCLAIMER_TEXT = "Napsala a namluvila umělá inteligence."
DISCLAIMER_STYLE = ""       # empty -> read plainly, bypassing the podcast GEMINI_STYLE
DISCLAIMER_TEMPO = 1.15     # ffmpeg atempo speed-up (0.5–2.0 is safe) for minimal disruption
DISCLAIMER_GAP_MS = 300     # silence between the notice and the jingle

# The visible half of the disclosure. The spoken notice covers listening; this
# covers clients that show a screen (which the Code of Practice asks for in
# addition to the audible disclaimer) and the AI-generated text of the show notes
# itself, since episodes publish without human editorial review.
AI_DISCLOSURE_LINE = (
    "Obsah napsala a namluvila umělá inteligence, bez lidské redakční úpravy."
)


def disclaimer_path(voice: str) -> Path:
    """Cache path for the AI-notice clip in a given voice."""
    return ASSETS / f"disclaimer_{voice}.wav"


# --- Intro jingle -----------------------------------------------------------
# A short sting prepended to every episode (after the AI notice). Set to None to
# disable. It is pre-normalized to the same loudness target as the voice, so they
# sit at a matched level.
JINGLE_FILE = ASSETS / "jingle.wav"
JINGLE_GAP_MS = 400  # silence between the jingle and the start of speech

# --- Audio output -----------------------------------------------------------
MP3_BITRATE = "64k"
MP3_SAMPLE_RATE = 24000  # Gemini TTS outputs 24 kHz PCM
MP3_CHANNELS = 1         # mono is plenty for speech

# ffmpeg audio post-processing applied to the speech during wav -> mp3 (set "" to
# disable). The pre-normalized jingle/notice clips are concatenated as-is and are
# not run through this filter.
#   adeclick  - removes any stray pops/clicks
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
