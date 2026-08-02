"""Turning everything the feeds offered into a short, varied shortlist."""

from __future__ import annotations

import datetime as dt
import re
import urllib.parse
from typing import Sequence

from agent.feeds import Entry

# Tracking parameters differ between feeds for the same article, so they are
# removed before two links are compared.
_TRACKING = re.compile(r"^(utm_|ref_?$|ref_src$|src$|cmpid$|fbclid$|gclid$)", re.I)
_NOISE = re.compile(r"[^a-z0-9 ]+")

# Some feeds (dev.to above all) carry posts in every script there is. The blog
# is written in English, so anything not in the Latin alphabet is left out.
_LETTER = re.compile(r"[^\W\d_]")
LATIN_SHARE = 0.6


def select(
    entries: Sequence[Entry],
    *,
    now: dt.datetime,
    window_hours: int = 26,
    per_feed_limit: int = 6,
    candidate_limit: int = 20,
) -> list[Entry]:
    """Pick the entries worth showing the model, newest and most varied first."""
    usable = [
        entry
        for entry in entries
        if _is_recent(entry, now=now, hours=window_hours) and _is_latin(entry.title)
    ]
    fresh_first = sorted(usable, key=_sort_key, reverse=True)

    by_source: dict[str, list[Entry]] = {}
    seen_links: set[str] = set()
    seen_titles: set[str] = set()

    for entry in fresh_first:
        link, title = _canonical_link(entry.link), _canonical_title(entry.title)
        if link in seen_links or title in seen_titles:
            continue
        seen_links.add(link)
        seen_titles.add(title)

        chosen = by_source.setdefault(entry.source, [])
        if len(chosen) < per_feed_limit:
            chosen.append(entry)

    return _interleave(list(by_source.values()))[:candidate_limit]


def _interleave(groups: list[list[Entry]]) -> list[Entry]:
    """Take one entry from each source in turn, so no single feed fills the list."""
    merged: list[Entry] = []
    for position in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if position < len(group):
                merged.append(group[position])
    return merged


def _is_recent(entry: Entry, *, now: dt.datetime, hours: int) -> bool:
    if entry.published is None:
        return True  # undated entries are rare; dropping them loses real stories
    return dt.timedelta() <= now - entry.published <= dt.timedelta(hours=hours)


def _is_latin(title: str) -> bool:
    """True when the title is written in the Latin alphabet."""
    letters = _LETTER.findall(title)
    if not letters:
        return False
    return sum(letter.isascii() for letter in letters) / len(letters) >= LATIN_SHARE


def _sort_key(entry: Entry) -> dt.datetime:
    # Undated entries sort last rather than crashing the comparison.
    return entry.published or dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def _canonical_link(link: str) -> str:
    parts = urllib.parse.urlsplit(link.strip())
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parts.query)
        if not _TRACKING.match(key)
    ]
    scheme = parts.scheme.lower()
    return urllib.parse.urlunsplit(
        (
            "https" if scheme == "http" else scheme,
            parts.netloc.lower().removeprefix("www."),
            parts.path.rstrip("/"),
            urllib.parse.urlencode(query),
            "",
        )
    )


def _canonical_title(title: str) -> str:
    return _NOISE.sub("", title.lower()).strip()
