"""The XML sitemap."""

from __future__ import annotations

from typing import Sequence

from ssg.posts import Post
from ssg.render import escape
from ssg.site import Site

SITEMAP_PATH = "sitemap.xml"


def build(site: Site, posts: Sequence[Post]) -> str:
    """List the home page and every post."""
    entries = [_entry(site.absolute(), posts[0].date.isoformat() if posts else None)]
    entries += [_entry(site.absolute(post.path), post.date.isoformat()) for post in posts]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def _entry(location: str, last_modified: str | None) -> str:
    modified = f"\n    <lastmod>{last_modified}</lastmod>" if last_modified else ""
    return f"  <url>\n    <loc>{escape(location)}</loc>{modified}\n  </url>"
