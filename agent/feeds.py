"""Reading RSS and Atom feeds with nothing but the standard library."""

from __future__ import annotations

import datetime as dt
import email.utils
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable, Iterable, Mapping
from xml.etree import ElementTree

USER_AGENT = "ti-blog-agent/1.0 (+https://github.com/OscarJuJi/ti-blog)"
TIMEOUT = 20
SUMMARY_LIMIT = 400

ATOM = "{http://www.w3.org/2005/Atom}"
DUBLIN_CORE = "{http://purl.org/dc/elements/1.1/}"


class FeedError(RuntimeError):
    """Raised when a feed cannot be read."""


@dataclass(frozen=True)
class Entry:
    """One story, as the feed described it."""

    title: str
    link: str
    summary: str
    published: dt.datetime | None
    source: str


def fetch(url: str, *, timeout: int = TIMEOUT) -> bytes:
    """Download a feed."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception as error:  # URLError, HTTPError, socket timeouts, bad TLS...
        raise FeedError(f"could not fetch {url}: {error}") from error


def parse(payload: bytes | str, *, source: str) -> list[Entry]:
    """Read either an RSS or an Atom document."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise FeedError(f"{source}: malformed XML: {error}") from error

    items = root.findall(".//item")
    if items:
        return [entry for entry in (_from_rss(item, source) for item in items) if entry]

    return [
        entry
        for entry in (_from_atom(item, source) for item in root.findall(f".//{ATOM}entry"))
        if entry
    ]


def collect(
    feeds: Iterable[Mapping[str, str]],
    *,
    timeout: int = TIMEOUT,
    on_error: Callable[[str], None] = print,
) -> list[Entry]:
    """Read every feed. A source that is down must not cost us the whole day."""
    entries: list[Entry] = []
    for feed in feeds:
        name, url = feed.get("name", feed.get("url", "?")), feed["url"]
        try:
            entries.extend(parse(fetch(url, timeout=timeout), source=name))
        except FeedError as error:
            on_error(f"skipping {name}: {error}")
    return entries


def _from_rss(item: ElementTree.Element, source: str) -> Entry | None:
    title = _clean(_text(item, "title"))
    link = _text(item, "link") or _text(item, "guid")
    if not title or not link:
        return None
    return Entry(
        title=title,
        link=link.strip(),
        summary=_summarize(_text(item, "description") or _text(item, f"{DUBLIN_CORE}description")),
        published=_moment(_text(item, "pubDate") or _text(item, f"{DUBLIN_CORE}date")),
        source=source,
    )


def _from_atom(item: ElementTree.Element, source: str) -> Entry | None:
    title = _clean(_text(item, f"{ATOM}title"))
    link = _atom_link(item)
    if not title or not link:
        return None
    return Entry(
        title=title,
        link=link,
        summary=_summarize(
            _text(item, f"{ATOM}summary") or _text(item, f"{ATOM}content")
        ),
        published=_moment(
            _text(item, f"{ATOM}published") or _text(item, f"{ATOM}updated")
        ),
        source=source,
    )


def _atom_link(item: ElementTree.Element) -> str:
    links = item.findall(f"{ATOM}link")
    for link in links:
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            return link.get("href", "").strip()
    return links[0].get("href", "").strip() if links else ""


def _text(element: ElementTree.Element, tag: str) -> str:
    found = element.find(tag)
    return (found.text or "").strip() if found is not None else ""


def _moment(raw: str) -> dt.datetime | None:
    """Read a publication date in either of the two formats feeds use."""
    if not raw:
        return None
    for read in (_rfc822, _iso8601):
        moment = read(raw)
        if moment is not None:
            return moment if moment.tzinfo else moment.replace(tzinfo=dt.timezone.utc)
    return None


def _rfc822(raw: str) -> dt.datetime | None:
    try:
        return email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def _iso8601(raw: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _summarize(raw: str) -> str:
    text = _clean(raw)
    return text if len(text) <= SUMMARY_LIMIT else f"{text[:SUMMARY_LIMIT].rstrip()}..."


def _clean(raw: str) -> str:
    """Feeds put HTML in places that are meant to be text. Take it back out."""
    if not raw:
        return ""
    stripper = _TextOnly()
    stripper.feed(raw)
    return " ".join(stripper.text().split())


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skipping = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skipping = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skipping = False

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)
