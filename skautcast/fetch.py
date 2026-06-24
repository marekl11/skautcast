"""Turn a saved newsletter HTML file into per-article JSON records.

Steps:
  1. Parse the newsletter, collect every <a href> plus title hints and the
     blurb text near each link.
  2. Follow each link (sparkpost tracking redirects resolve to skaut.cz).
  3. Keep only real article URLs, dedupe, and skip anything already in history.
  4. Extract clean article text with trafilatura. If the page is a login wall
     (too little text), fall back to the newsletter's own blurb.
  5. Write data/articles/<hash>.json and record the article in state.json.

Usage:
    python -m skautcast.fetch data/inbox/<msgid>.html [--subject "..."] [--msgid ID]
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
import trafilatura
from bs4 import BeautifulSoup

from . import config, state

IMG_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp|svg)$", re.I)


# --- title / blurb hint helpers --------------------------------------------
def slug_title(url: str) -> str:
    seg = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    seg = re.sub(r"[-_]+", " ", seg).strip()
    return seg[:1].upper() + seg[1:] if seg else ""


def img_title(a_tag) -> str:
    img = a_tag.find("img")
    if not img or not img.get("src"):
        return ""
    name = unquote(urlparse(img["src"]).path.rsplit("/", 1)[-1])
    name = IMG_EXT_RE.sub("", name)
    name = re.sub(r"^novinky[-_]?", "", name, flags=re.I)
    name = re.sub(r"[-_]+", " ", name).strip()
    return name[:1].upper() + name[1:] if name else ""


def nearby_text(a_tag) -> str:
    node = a_tag
    for _ in range(6):
        node = node.parent
        if node is None:
            break
        txt = node.get_text(" ", strip=True)
        if 60 <= len(txt) <= 1500:
            return txt
    return a_tag.get_text(" ", strip=True)


def extract_links(page_html: str, final_url: str, key: str) -> list[dict]:
    """Author-curated links from the article body (markdown links via trafilatura),
    as [{text, url}], excluding the article's own URL and images."""
    out: list[dict] = []
    try:
        md = trafilatura.extract(
            page_html, url=final_url, output_format="markdown",
            include_links=True, include_comments=False, include_tables=False,
        ) or ""
    except Exception:
        return out
    seen = set()
    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", md):
        text, u = m.group(1).strip(), m.group(2)
        if u.rstrip("/") == key or u in seen or IMG_EXT_RE.search(u):
            continue
        seen.add(u)
        out.append({"text": text[:80], "url": u})
        if len(out) >= 8:
            break
    return out


# --- link resolution + filtering -------------------------------------------
def is_article_url(final_url: str) -> bool:
    p = urlparse(final_url)
    host, path = p.netloc.lower(), p.path.lower()
    if not any(host.endswith(s) for s in config.ALLOW_HOST_SUFFIXES):
        return False
    if any(host.endswith(s) for s in config.BLOCK_HOST_SUFFIXES):
        return False
    if any(s in path for s in config.BLOCK_PATH_SUBSTR):
        return False
    # ignore links straight to a file/image
    if IMG_EXT_RE.search(path) or path.endswith((".pdf", ".zip")):
        return False
    return True


def normalize(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def resolve(session, url):
    try:
        r = session.get(url, allow_redirects=True, timeout=config.HTTP_TIMEOUT)
        return r.url, r.text
    except requests.RequestException as exc:
        print(f"  ! could not resolve {url[:60]}... ({exc})")
        return None, None


# --- main -------------------------------------------------------------------
def fetch(html_path: Path, msgid: str, subject: str) -> list[dict]:
    config.ensure_dirs()
    st = state.load_state()

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT

    seen_final = set()
    pending = []
    resolved_cache: dict[str, str | None] = {}

    anchors = [a for a in soup.find_all("a", href=True)]
    print(f"Newsletter '{subject}' — {len(anchors)} links, resolving article links ...")

    for a in anchors:
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "#")):
            continue

        if href in resolved_cache:
            final_url = resolved_cache[href]
            page_html = None
        else:
            final_url, page_html = resolve(session, href)
            resolved_cache[href] = final_url
            time.sleep(config.HTTP_DELAY)

        if not final_url or not is_article_url(final_url):
            continue

        key = normalize(final_url)
        if key in seen_final:
            continue
        seen_final.add(key)

        h = state.url_hash(key)
        if h in st["episodes"]:
            print(f"  = already done: {final_url[:70]}")
            continue

        # extract the article body
        article_text = ""
        title = ""
        image_url = ""
        links = []
        if page_html:
            article_text = trafilatura.extract(
                page_html, url=final_url,
                include_comments=False, include_tables=False,
            ) or ""
            try:
                md = trafilatura.extract_metadata(page_html)
                if md:
                    if md.title:
                        title = md.title.strip()
                    if getattr(md, "image", None):
                        image_url = md.image  # og:image -> episode artwork
            except Exception:
                pass
            links = extract_links(page_html, final_url, key)

        source = "article"
        if len(article_text) < config.MIN_ARTICLE_CHARS:
            source = "newsletter_blurb"
            article_text = nearby_text(a)

        if not title:
            title = slug_title(final_url) or img_title(a) or \
                a.get_text(" ", strip=True) or "Skautská novinka"

        record = {
            "hash": h,
            "url": key,
            "title_hint": title,
            "source": source,
            "article_text": article_text,
            "image_url": image_url,
            "links": links,
            "newsletter_subject": subject,
            "newsletter_msgid": msgid,
            "fetched_at": state.now_iso(),
        }
        (config.ARTICLES / f"{h}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        st["episodes"][h] = {
            "url": key,
            "title": title,
            "image_url": image_url,
            "links": links,
            "first_seen": record["fetched_at"],
            "newsletter_subject": subject,
            "newsletter_msgid": msgid,
            "article_path": str((config.ARTICLES / f"{h}.json").relative_to(config.ROOT)),
            "summary_path": None,
            "audio_path": None,
            "audio_bytes": None,
            "duration_sec": None,
            "status": "fetched",
        }
        pending.append({"hash": h, "title": title, "source": source})
        print(f"  + NEW [{source:16}] {title}")

    state.mark_newsletter(st, msgid)
    state.save_state(st)
    config.PENDING_FILE.write_text(
        json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pending


def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    html_path = Path(argv[0])
    msgid, subject = html_path.stem, html_path.stem
    if "--msgid" in argv:
        msgid = argv[argv.index("--msgid") + 1]
    if "--subject" in argv:
        subject = argv[argv.index("--subject") + 1]

    pending = fetch(html_path, msgid, subject)
    print(f"\n{len(pending)} new article(s) need a summary "
          f"(data/articles/<hash>.json -> data/summaries/<hash>.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
