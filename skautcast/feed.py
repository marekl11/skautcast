"""Generate the podcast RSS feed (docs/feed.xml) from state.json."""
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import requests
from feedgen.feed import FeedGenerator

from . import config, state


def _fit_image(src: Path) -> Path:
    """Shrink an episode image to IMAGE_MAX_PX on its long side and store it as
    JPEG (docs/img/<hash>.jpg), returning the path it ends up at. Article photos
    often come straight off a camera — 6000x4000 and 24 MB — while players and the
    Skautban grid show them a few hundred pixels wide. A JPEG that is already small
    enough is left alone, so rebuilding the feed rewrites nothing; one that cannot
    be read is left alone as well, as it was before."""
    from PIL import Image, ImageOps

    try:
        with Image.open(src) as opened:
            if src.suffix == ".jpg" and max(opened.size) <= config.IMAGE_MAX_PX:
                return src
            # A camera may store the photo sideways with a note to turn it. The note
            # does not survive re-encoding, so the turn is done now.
            im = ImageOps.exif_transpose(opened)
    except OSError:
        return src
    im.thumbnail((config.IMAGE_MAX_PX, config.IMAGE_MAX_PX), Image.LANCZOS)
    if im.mode != "RGB":
        # JPEG has no transparency: whatever is see-through goes onto white.
        rgba = im.convert("RGBA")
        im = Image.new("RGB", rgba.size, (255, 255, 255))
        im.paste(rgba, mask=rgba.getchannel("A"))
    dst = src.with_suffix(".jpg")
    im.save(dst, "JPEG", quality=config.IMAGE_QUALITY, optimize=True, progressive=True)
    if dst != src:
        src.unlink()
    return dst


def _ensure_image(h: str, url: str):
    """Download an episode's article image into docs/img/<hash>.jpg and return
    its Pages URL. Self-hosting avoids feedgen's png/jpg-extension requirement and
    keeps artwork available even if the source moves it. Images kept from before
    they were shrunk (large, or PNG) are shrunk here on the next build."""
    if not url or not url.startswith("http"):
        return None
    imgdir = config.DOCS / "img"
    imgdir.mkdir(parents=True, exist_ok=True)
    for ext in ("jpg", "png"):
        if (imgdir / f"{h}.{ext}").exists():
            return f"{config.BASE_URL}/img/{_fit_image(imgdir / f'{h}.{ext}').name}"
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": config.USER_AGENT})
        if r.status_code != 200:
            return None
        # Podcast artwork must be JPEG or PNG. Map the content type explicitly and
        # skip anything else (webp/gif/untyped) so it falls back to the channel cover
        # instead of shipping mislabeled bytes clients can't decode.
        ctype = r.headers.get("Content-Type", "").lower()
        if "png" in ctype:
            ext = "png"
        elif "jpeg" in ctype or "jpg" in ctype:
            ext = "jpg"
        else:
            return None
        (imgdir / f"{h}.{ext}").write_bytes(r.content)
        return f"{config.BASE_URL}/img/{_fit_image(imgdir / f'{h}.{ext}').name}"
    except requests.RequestException:
        return None


def ensure_cover() -> None:
    """Create a simple placeholder cover (1400x1400) if none exists yet."""
    if config.COVER_FILE.exists():
        return
    from PIL import Image, ImageDraw, ImageFont

    config.COVER_FILE.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1400, 1400), (16, 79, 45))  # skaut-ish green
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 180)
    except Exception:
        font = ImageFont.load_default()
    text = "SkautCast"
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((1400 - (box[2] - box[0])) / 2, (1400 - (box[3] - box[1])) / 2 - 40),
              text, fill=(255, 255, 255), font=font)
    img.save(config.COVER_FILE)


def _episode_description(ep: dict) -> str:
    """Show notes, as a small HTML document: the AI disclosure, then the source link
    (plus any hand-picked `extra_links`) and a short blurb of what the episode says.

    Podcast clients render a limited HTML subset (p, a, b, i, lists), which is what
    gives us the blank lines between paragraphs and a clickable link — plain text
    would show the URL as dead characters. The blurb is deliberately a couple of
    sentences, not the transcript: it should be readable in ~20 seconds so someone
    can decide whether to spend the two minutes listening.
    """
    blurb = ep.get("blurb") or _first_paragraph(ep.get("summary_text") or "")
    parts = [f"<p>{escape(config.AI_DISCLOSURE_LINE)}</p>"]

    # Link first so it doesn't get lost under the text, with the blurb on the very next
    # line: a <br> keeps them in one paragraph, where a second <p> would push the blurb
    # a blank line away and bury the link again.
    second = []
    if ep.get("url"):
        second.append(f'<a href="{escape(ep["url"], quote=True)}">Přečíst celý článek</a>')
    # Hand-picked extras set per episode in state.json (e.g. a Facebook post about the
    # article). Deliberately separate from the auto-extracted `links`, which stay out.
    for link in ep.get("extra_links") or []:
        second.append(f'<a href="{escape(link["url"], quote=True)}">{escape(link["text"])}</a>')
    if blurb:
        second.append(escape(blurb))
    if second:
        parts.append("<p>" + "<br>".join(second) + "</p>")
    return "\n".join(parts)


def _first_paragraph(text: str) -> str:
    """Fallback blurb for summaries written before the `> blurb` block existed."""
    for para in text.split("\n"):
        if para.strip():
            return para.strip()
    return ""


def _pubdate(iso: str) -> datetime:
    try:
        dt = datetime.fromisoformat(iso)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def build_feed() -> int:
    st = state.load_state()
    ensure_cover()

    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(config.FEED_TITLE)
    fg.link(href=config.BASE_URL, rel="alternate")
    fg.link(href=f"{config.BASE_URL}/feed.xml", rel="self")
    fg.description(config.FEED_DESCRIPTION)
    fg.language(config.FEED_LANGUAGE)
    fg.author({"name": config.FEED_AUTHOR, "email": config.FEED_EMAIL})
    cover_url = f"{config.BASE_URL}/{config.COVER_FILE.name}"
    fg.logo(cover_url)
    fg.podcast.itunes_image(cover_url)
    fg.podcast.itunes_subtitle(config.FEED_SUBTITLE)
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_author(config.FEED_AUTHOR)
    fg.podcast.itunes_category(config.FEED_CATEGORY)
    fg.podcast.itunes_owner(name=config.FEED_AUTHOR, email=config.FEED_EMAIL)

    published = [
        (h, ep) for h, ep in st["episodes"].items()
        if ep.get("status") == "published" and ep.get("audio_path")
    ]
    # newest first
    published.sort(key=lambda kv: kv[1].get("first_seen", ""), reverse=True)

    for h, ep in published:
        fe = fg.add_entry()
        fe.id(h)
        fe.guid(h, permalink=False)
        fe.title(ep.get("title") or "Skautská novinka")
        fe.description(_episode_description(ep))
        fe.pubDate(_pubdate(ep.get("first_seen", "")))
        if ep.get("url"):
            fe.link(href=ep["url"])
        img = _ensure_image(h, ep.get("image_url"))
        if img:
            fe.podcast.itunes_image(img)
        # ?v=<bytes> changes whenever the audio changes, so podcast clients
        # re-download instead of keeping a stale cached file.
        ver = ep.get("audio_bytes") or 0
        fe.enclosure(
            f"{config.BASE_URL}/{ep['audio_path']}?v={ver}",
            str(ver),
            "audio/mpeg",
        )
        if ep.get("duration_sec"):
            fe.podcast.itunes_duration(int(ep["duration_sec"]))

    config.FEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(config.FEED_FILE), pretty=True)
    print(f"[feed] wrote {config.FEED_FILE} with {len(published)} episode(s)")
    return len(published)


if __name__ == "__main__":
    raise SystemExit(0 if build_feed() >= 0 else 1)
