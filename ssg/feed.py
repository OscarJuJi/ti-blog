"""The RSS 2.0 feed, assembled by hand."""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from ssg.posts import Post
from ssg.render import escape
from ssg.site import Site

FEED_PATH = "feed.xml"

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def build(site: Site, posts: Sequence[Post], *, built_at: dt.datetime) -> str:
    """Render the feed for *posts*, newest first."""
    items = "\n".join(_item(site, post) for post in posts)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{escape(site.title)}</title>\n"
        f"    <link>{escape(site.absolute())}</link>\n"
        f"    <description>{escape(site.description)}</description>\n"
        f"    <language>{escape(site.language)}</language>\n"
        f"    <lastBuildDate>{rfc822(built_at)}</lastBuildDate>\n"
        f'    <atom:link href="{escape(site.absolute(FEED_PATH))}"'
        ' rel="self" type="application/rss+xml"/>\n'
        f"{items}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def _item(site: Site, post: Post) -> str:
    link = site.absolute(post.path)
    published = dt.datetime.combine(post.date, dt.time(), tzinfo=dt.timezone.utc)
    categories = "".join(
        f"\n      <category>{escape(tag)}</category>" for tag in post.tags
    )
    return (
        "    <item>\n"
        f"      <title>{escape(post.title)}</title>\n"
        f"      <link>{escape(link)}</link>\n"
        f'      <guid isPermaLink="true">{escape(link)}</guid>\n'
        f"      <pubDate>{rfc822(published)}</pubDate>\n"
        f"      <description>{escape(post.summary)}</description>"
        f"{categories}\n"
        "    </item>"
    )


def rfc822(moment: dt.datetime) -> str:
    """Format a moment as RSS wants it, in English whatever the machine's locale."""
    utc = moment.astimezone(dt.timezone.utc) if moment.tzinfo else moment
    return (
        f"{_DAYS[utc.weekday()]}, {utc.day:02d} {_MONTHS[utc.month - 1]} {utc.year} "
        f"{utc.hour:02d}:{utc.minute:02d}:{utc.second:02d} +0000"
    )
