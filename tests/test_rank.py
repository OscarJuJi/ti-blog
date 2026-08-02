import datetime as dt

from agent import rank
from agent.feeds import Entry

NOW = dt.datetime(2026, 8, 1, 12, 0, tzinfo=dt.timezone.utc)


def entry(title, *, link=None, source="A", hours_ago=1):
    return Entry(
        title=title,
        link=link or f"https://example.com/{title.lower().replace(' ', '-')}",
        summary="",
        published=NOW - dt.timedelta(hours=hours_ago),
        source=source,
    )


def titles(entries):
    return [item.title for item in entries]


def test_drops_entries_older_than_the_window():
    chosen = rank.select(
        [entry("Fresh", hours_ago=2), entry("Stale", hours_ago=40)],
        now=NOW,
        window_hours=26,
    )
    assert titles(chosen) == ["Fresh"]


def test_drops_entries_dated_in_the_future():
    chosen = rank.select([entry("Tomorrow", hours_ago=-5)], now=NOW, window_hours=26)
    assert chosen == []


def test_keeps_undated_entries():
    undated = Entry(title="No date", link="https://x.example/a", summary="", published=None, source="A")
    assert titles(rank.select([undated], now=NOW)) == ["No date"]


def test_newest_first():
    chosen = rank.select(
        [entry("Older", hours_ago=8), entry("Newer", hours_ago=1)], now=NOW
    )
    assert titles(chosen) == ["Newer", "Older"]


def test_removes_the_same_link_seen_twice():
    chosen = rank.select(
        [
            entry("Story", link="https://example.com/a", source="A"),
            entry("Same story elsewhere", link="https://www.example.com/a/?utm_source=rss", source="B"),
        ],
        now=NOW,
    )
    assert titles(chosen) == ["Story"]


def test_removes_the_same_headline_from_two_feeds():
    chosen = rank.select(
        [
            entry("Rust 2.0 ships", link="https://one.example/x", source="A"),
            entry("rust 2.0 ships!", link="https://two.example/y", source="B"),
        ],
        now=NOW,
    )
    assert len(chosen) == 1


def test_caps_how_much_a_single_feed_contributes():
    entries = [entry(f"Story {index}", source="Loud") for index in range(10)]
    assert len(rank.select(entries, now=NOW, per_feed_limit=3)) == 3


def test_sources_take_turns_so_one_feed_cannot_fill_the_list():
    entries = [entry(f"Loud {index}", source="Loud", hours_ago=1) for index in range(4)]
    entries += [entry(f"Quiet {index}", source="Quiet", hours_ago=5) for index in range(2)]

    sources = [item.source for item in rank.select(entries, now=NOW)]

    assert sources[:4] == ["Loud", "Quiet", "Loud", "Quiet"]


def test_honours_the_candidate_limit():
    entries = [entry(f"S{index}", source=f"Feed{index}") for index in range(30)]
    assert len(rank.select(entries, now=NOW, candidate_limit=8)) == 8


def test_no_entries_no_crash():
    assert rank.select([], now=NOW) == []


def test_drops_titles_that_are_not_in_the_latin_alphabet():
    chosen = rank.select(
        [
            entry("Go generics explained", link="https://x.example/1"),
            entry("iota ใน Go อักษรกรีกตัวจิ๋ว", link="https://x.example/2"),
            entry("LLM中如果一个问题容易验证", link="https://x.example/3"),
        ],
        now=NOW,
    )
    assert titles(chosen) == ["Go generics explained"]


def test_keeps_a_latin_title_carrying_accents():
    chosen = rank.select([entry("Ceci n'est pas un pipeline, résumé")], now=NOW)
    assert len(chosen) == 1
