"""History / state store.

state.json remembers every article ever turned into an episode, so we never
redo one. It is keyed by a short hash of the resolved article URL.
"""
import json
import hashlib
from datetime import datetime, timezone

from . import config


def url_hash(url: str) -> str:
    """Stable short id for an article, derived from its resolved URL."""
    return hashlib.sha1(url.strip().lower().encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return {"newsletters_seen": [], "episodes": {}}


def save_state(state: dict) -> None:
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def is_known(state: dict, url: str) -> bool:
    return url_hash(url) in state["episodes"]


def newsletter_seen(state: dict, msgid: str) -> bool:
    return msgid in state.get("newsletters_seen", [])


def mark_newsletter(state: dict, msgid: str) -> None:
    state.setdefault("newsletters_seen", [])
    if msgid not in state["newsletters_seen"]:
        state["newsletters_seen"].append(msgid)
