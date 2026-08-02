import datetime as dt

import pytest

from agent import feeds

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <item>
      <title>Rust 2.0 ships &amp; breaks everything</title>
      <link>https://example.com/rust-2</link>
      <description>&lt;p&gt;The release &lt;b&gt;lands&lt;/b&gt; today.&lt;/p&gt;</description>
      <pubDate>Sat, 01 Aug 2026 09:30:00 +0000</pubDate>
    </item>
    <item>
      <title>A second story</title>
      <link>https://example.com/second</link>
      <description>Plain text summary.</description>
      <pubDate>Fri, 31 Jul 2026 22:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Example</title>
  <entry>
    <title>An Atom story</title>
    <link rel="alternate" href="https://atom.example/story"/>
    <link rel="edit" href="https://atom.example/edit"/>
    <summary>Summary of the story.</summary>
    <published>2026-08-01T06:15:00Z</published>
  </entry>
</feed>
"""


def test_reads_an_rss_feed():
    entries = feeds.parse(RSS, source="Example News")

    assert len(entries) == 2
    first = entries[0]
    assert first.title == "Rust 2.0 ships & breaks everything"
    assert first.link == "https://example.com/rust-2"
    assert first.summary == "The release lands today."
    assert first.published == dt.datetime(2026, 8, 1, 9, 30, tzinfo=dt.timezone.utc)
    assert first.source == "Example News"


def test_reads_an_atom_feed_and_prefers_the_alternate_link():
    (entry,) = feeds.parse(ATOM, source="Atom Example")

    assert entry.title == "An Atom story"
    assert entry.link == "https://atom.example/story"
    assert entry.published == dt.datetime(2026, 8, 1, 6, 15, tzinfo=dt.timezone.utc)


def test_html_is_taken_out_of_summaries():
    payload = RSS.replace(
        "Plain text summary.",
        "&lt;div&gt;Text&lt;script&gt;alert(1)&lt;/script&gt; after&lt;/div&gt;",
    )
    assert feeds.parse(payload, source="x")[1].summary == "Text after"


def test_long_summaries_are_cut():
    payload = RSS.replace("Plain text summary.", "word " * 200)
    summary = feeds.parse(payload, source="x")[1].summary
    assert len(summary) <= feeds.SUMMARY_LIMIT + 3
    assert summary.endswith("...")


def test_entries_without_a_title_or_link_are_dropped():
    payload = RSS.replace("<link>https://example.com/second</link>", "")
    assert len(feeds.parse(payload, source="x")) == 1


def test_an_undated_entry_still_loads():
    payload = RSS.replace("<pubDate>Sat, 01 Aug 2026 09:30:00 +0000</pubDate>", "")
    assert feeds.parse(payload, source="x")[0].published is None


def test_malformed_xml_is_an_error():
    with pytest.raises(feeds.FeedError, match="malformed XML"):
        feeds.parse("<rss><channel>", source="x")


def test_collect_skips_a_feed_that_is_down(monkeypatch):
    def fetch(url, timeout=None):
        if "broken" in url:
            raise feeds.FeedError("503")
        return RSS

    monkeypatch.setattr(feeds, "fetch", fetch)
    problems = []

    entries = feeds.collect(
        [
            {"name": "Broken", "url": "https://broken.example/feed"},
            {"name": "Working", "url": "https://ok.example/feed"},
        ],
        on_error=problems.append,
    )

    assert [entry.source for entry in entries] == ["Working", "Working"]
    assert problems and "Broken" in problems[0]
