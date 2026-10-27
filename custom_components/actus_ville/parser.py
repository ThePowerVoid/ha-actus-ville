"""Parse RSS 2.0 and Atom feeds into posts, using only the standard library."""

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree

MAX_TEXT_LENGTH = 1000

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
}
_ATOM_FEED_TAG = f"{{{_NS['atom']}}}feed"
_OLDEST = datetime.min.replace(tzinfo=UTC)
_BLOCK_TAGS = frozenset(
    {"p", "div", "li", "blockquote", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
)
_SKIPPED_TAGS = frozenset({"script", "style"})


class FeedError(Exception):
    """The document is not a readable RSS or Atom feed."""


@dataclass(slots=True)
class Post:
    """A single publication from the feed."""

    id: str
    title: str
    text: str
    link: str | None
    image: str | None
    published: datetime | None
    keywords: list[str] = field(default_factory=list)

    @property
    def important(self) -> bool:
        return bool(self.keywords)

    def as_dict(self) -> dict[str, Any]:
        text = self.text
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH].rstrip() + "…"
        return {
            "id": self.id,
            "date": self.published.isoformat() if self.published else None,
            "text": text,
            "link": self.link,
            "image": self.image,
            "important": self.important,
            "keywords": list(self.keywords),
        }


def parse_feed(raw: bytes, keywords: Iterable[str] = ()) -> list[Post]:
    """Return the feed's posts, newest first, flagged with the keywords they contain."""
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as err:
        raise FeedError(f"Unreadable feed: {err}") from err

    if root.tag == "rss":
        posts = [_parse_rss_item(item) for item in root.iterfind("channel/item")]
    elif root.tag == _ATOM_FEED_TAG:
        posts = [_parse_atom_entry(entry) for entry in root.iterfind("atom:entry", _NS)]
    else:
        raise FeedError(f"Unsupported feed format: <{root.tag}>")

    keywords = list(keywords)
    for post in posts:
        post.keywords = find_keywords(f"{post.title}\n{post.text}", keywords)
    posts.sort(key=lambda post: post.published or _OLDEST, reverse=True)
    return posts


def find_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    """Return the keywords found as whole words, ignoring case, accents and an s/x plural."""
    haystack = _normalize(text)
    return [
        keyword
        for keyword in keywords
        if (needle := _normalize(keyword).strip())
        and re.search(rf"\b{re.escape(needle)}[sx]?\b", haystack)
    ]


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _parse_rss_item(item: ElementTree.Element) -> Post:
    title = _clean(item.findtext("title"))
    html = item.findtext("content:encoded", namespaces=_NS) or item.findtext("description")
    text, inline_image = _html_to_text(html or "")
    link = _clean(item.findtext("link")) or None
    return Post(
        id=_clean(item.findtext("guid")) or link or _digest(title, text),
        title=title,
        text=text or title,
        link=link,
        image=_media_image(item) or inline_image,
        published=_parse_rfc822(item.findtext("pubDate")),
    )


def _parse_atom_entry(entry: ElementTree.Element) -> Post:
    title = _clean(entry.findtext("atom:title", namespaces=_NS))
    html = entry.findtext("atom:content", namespaces=_NS) or entry.findtext(
        "atom:summary", namespaces=_NS
    )
    text, inline_image = _html_to_text(html or "")
    link = next(
        (
            element.get("href")
            for element in entry.iterfind("atom:link", _NS)
            if element.get("rel", "alternate") == "alternate"
        ),
        None,
    )
    published = entry.findtext("atom:published", namespaces=_NS) or entry.findtext(
        "atom:updated", namespaces=_NS
    )
    return Post(
        id=_clean(entry.findtext("atom:id", namespaces=_NS)) or link or _digest(title, text),
        title=title,
        text=text or title,
        link=link,
        image=_media_image(entry) or inline_image,
        published=_parse_iso(published),
    )


def _media_image(element: ElementTree.Element) -> str | None:
    for media in element.iterfind("media:content", _NS):
        if media.get("medium") == "image" or media.get("type", "").startswith("image/"):
            if url := _http_url(media.get("url")):
                return url
    for thumbnail in element.iterfind("media:thumbnail", _NS):
        if url := _http_url(thumbnail.get("url")):
            return url
    for enclosure in element.iterfind("enclosure"):
        if enclosure.get("type", "").startswith("image/"):
            if url := _http_url(enclosure.get("url")):
                return url
    return None


class _HtmlToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.image: str | None = None
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag == "br":
            self._parts.append("\n")
        elif tag == "img" and self.image is None:
            self.image = _http_url(dict(attrs).get("src"))

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._parts).splitlines())
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _html_to_text(html: str) -> tuple[str, str | None]:
    converter = _HtmlToText()
    converter.feed(html)
    converter.close()
    return converter.text(), converter.image


def _parse_rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _as_utc(parsedate_to_datetime(value.strip()))
    except (TypeError, ValueError):
        return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.strip()))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _http_url(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value.startswith(("https://", "http://")) else None


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _digest(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]
