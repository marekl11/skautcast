"""Turn a downloaded .eml newsletter into the HTML + meta pair that fetch.py reads.

Gmail's "Download message" gives a raw MIME file. fetch.py wants the newsletter's
HTML body plus a small meta record, named by message id — the same shape the older
mail-connector path produced. This bridges the two, so a newsletter that can't be
pulled through an API can still be dropped in by hand.

Usage:
    python -m skautcast.eml data/eml/*.eml
"""
import email
import email.policy
import hashlib
import json
import sys
from pathlib import Path

from . import config


def _msg_id(msg) -> str:
    """Stable id for the message: prefer its Message-ID, else hash the subject+date.

    fetch.py records this against every article, so it must not change between runs
    or the same newsletter would import twice.
    """
    raw = msg.get("Message-ID") or f"{msg.get('Subject')}|{msg.get('Date')}"
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


def _html_body(msg) -> str | None:
    """The richest HTML part. Newsletters are multipart/alternative; the plaintext
    twin loses the links we need, so HTML only."""
    if msg.is_multipart():
        best = None
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                body = part.get_content()
                if best is None or len(body) > len(best):
                    best = body
        return best
    return msg.get_content() if msg.get_content_type() == "text/html" else None


def convert(eml_path: Path) -> tuple[Path, dict] | None:
    msg = email.message_from_bytes(eml_path.read_bytes(), policy=email.policy.default)
    html = _html_body(msg)
    if not html:
        print(f"[eml] no HTML part in {eml_path.name}, skipped")
        return None

    mid = _msg_id(msg)
    config.INBOX.mkdir(parents=True, exist_ok=True)
    out = config.INBOX / f"{mid}.html"
    out.write_text(html, encoding="utf-8")

    date = msg.get("Date")
    try:
        date = email.utils.parsedate_to_datetime(date).isoformat()
    except Exception:
        pass
    meta = {
        "id": mid,
        "subject": str(msg.get("Subject") or "").strip(),
        "date": date,
        "sender": email.utils.parseaddr(msg.get("From") or "")[1],
    }
    (config.INBOX / f"{mid}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[eml] {out.name}  <-  {meta['subject'][:60]}")
    return out, meta


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv]
    if not paths:
        print(__doc__)
        return 1
    ok = 0
    for p in sorted(paths):
        if convert(p):
            ok += 1
    print(f"[eml] converted {ok}/{len(paths)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
