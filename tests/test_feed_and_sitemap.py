import datetime as dt
from pathlib import Path
from xml.etree import ElementTree

import pytest

from ssg import feed, sitemap
from ssg.posts import Post
from ssg.site import Site

SITE = Site.from_config(
    {
        "site": {
            "title": "IT Brief",
            "description": "Daily tech news.",
            "url": "https://oscarjuji.github.io",
            "base_url": "/ti-blog",
            "language": "en",
        }
    }
)

POSTS = [
    Post(
        slug="daily-digest",
        title="Daily digest & more",
        date=dt.date(2026, 8, 1),
        description="Five stories.",
        tags=("digest", "news"),
        body="Body.",
        source=Path("a.md"),
    ),
    Post(
        slug="older-note",
        title="Older note",
        date=dt.date(2026, 7, 30),
        description="",
        tags=(),
        body="## Heading\n\nThe opening paragraph of the body.",
        source=Path("b.md"),
    ),
]

BUILT_AT = dt.datetime(2026, 8, 1, 13, 5, 0, tzinfo=dt.timezone.utc)


def test_feed_is_well_formed_xml_with_one_item_per_post():
    root = ElementTree.fromstring(feed.build(SITE, POSTS, built_at=BUILT_AT))
    channel = root.find("channel")

    assert channel.findtext("title") == "IT Brief"
    items = channel.findall("item")
    assert len(items) == 2
    assert items[0].findtext("title") == "Daily digest & more"
    assert items[0].findtext("link") == "https://oscarjuji.github.io/ti-blog/posts/daily-digest/"
    assert items[0].findtext("pubDate") == "Sat, 01 Aug 2026 00:00:00 +0000"
    assert [category.text for category in items[0].findall("category")] == ["digest", "news"]


def test_feed_falls_back_to_the_body_when_a_post_has_no_description():
    root = ElementTree.fromstring(feed.build(SITE, POSTS, built_at=BUILT_AT))
    second = root.find("channel").findall("item")[1]
    assert second.findtext("description") == "The opening paragraph of the body."


def test_feed_survives_having_no_posts():
    root = ElementTree.fromstring(feed.build(SITE, [], built_at=BUILT_AT))
    assert root.find("channel").findall("item") == []


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc), "Sat, 01 Aug 2026 00:00:00 +0000"),
        (dt.datetime(2026, 1, 5, 9, 7, 3, tzinfo=dt.timezone.utc), "Mon, 05 Jan 2026 09:07:03 +0000"),
    ],
)
def test_rfc822_dates_are_english_regardless_of_locale(moment, expected):
    assert feed.rfc822(moment) == expected


def test_sitemap_lists_the_home_page_and_every_post():
    root = ElementTree.fromstring(sitemap.build(SITE, POSTS))
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = [url.findtext("s:loc", namespaces=namespace) for url in root.findall("s:url", namespace)]

    assert locations == [
        "https://oscarjuji.github.io/ti-blog/",
        "https://oscarjuji.github.io/ti-blog/posts/daily-digest/",
        "https://oscarjuji.github.io/ti-blog/posts/older-note/",
    ]


def test_sitemap_survives_having_no_posts():
    root = ElementTree.fromstring(sitemap.build(SITE, []))
    assert len(root) == 1
