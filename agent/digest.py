"""Turning a shortlist of feed entries into the Markdown of the day's post.

The model never writes a URL. It answers with JSON that points at entries by
index, and the links in the published post are copied from the feeds themselves.
A model can therefore get a summary wrong -- it cannot invent a source.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Callable, Sequence

from agent.feeds import Entry
from agent.llm import LLM, LLMError
from ssg.posts import format_date

TAGS = ("digest", "news")
MIN_USABLE_STORIES = 3
DESCRIPTION_LIMIT = 200

SYSTEM = (
    "You write the daily technology digest for a working software engineer's blog. "
    "You are accurate before you are interesting, and you never pad."
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class DigestError(RuntimeError):
    """Raised when the model's answer cannot be turned into a digest."""


@dataclass(frozen=True)
class Story:
    """One item of the digest: the model's words over a real entry."""

    entry: Entry
    headline: str
    summary: str


def build(
    day: dt.date,
    entries: Sequence[Entry],
    *,
    llm: LLM | None = None,
    min_stories: int = 5,
    max_stories: int = 10,
    on_error: Callable[[str], None] = print,
) -> str:
    """Return the Markdown file for *day*, falling back to links if need be."""
    if not entries:
        raise DigestError("no entries to write about")

    if llm is not None:
        try:
            intro, stories = write(
                llm, entries, day=day, min_stories=min_stories, max_stories=max_stories
            )
            return render(day, intro, stories)
        except (LLMError, DigestError) as error:
            on_error(f"writing links only: {error}")

    return render_links(day, entries[:max_stories])


def write(
    llm: LLM,
    entries: Sequence[Entry],
    *,
    day: dt.date,
    min_stories: int,
    max_stories: int,
) -> tuple[str, list[Story]]:
    """Ask the model to choose and summarize, and check what comes back."""
    answer = llm.generate(
        prompt(entries, day=day, min_stories=min_stories, max_stories=max_stories),
        system=SYSTEM,
    )
    payload = _json(answer)

    intro = str(payload.get("intro", "")).strip()
    stories = _stories(payload.get("stories"), entries, limit=max_stories)
    # A digest of one or two items is not worth publishing -- unless that is all
    # the configuration ever asked for.
    floor = min(MIN_USABLE_STORIES, max_stories)
    if len(stories) < floor:
        raise DigestError(f"only {len(stories)} usable stories came back")
    return intro, stories


def prompt(
    entries: Sequence[Entry], *, day: dt.date, min_stories: int, max_stories: int
) -> str:
    """The whole instruction, candidates included."""
    candidates = "\n\n".join(
        f"[{number}] {entry.title}\n"
        f"    source: {entry.source}\n"
        f"    link: {entry.link}\n"
        f"    feed summary: {entry.summary or '(none)'}"
        for number, entry in enumerate(entries, start=1)
    )
    return f"""Today is {format_date(day)}. Below are {len(entries)} stories \
pulled from technology news feeds in the last day.

Choose the {min_stories} to {max_stories} that matter most to a working software \
engineer, and write the digest.

Rules:
- Base every summary only on the title and feed summary given. If they are thin, \
say only what the headline supports. Never invent details, numbers, quotes or names.
- Two or three sentences per story. Say what happened and why a developer should \
care. No hype, no filler openings like "In a move that".
- Prefer a spread of topics over five variations of the same story.
- Skip press releases, funding announcements without substance, and pure marketing.
- Rewrite each headline in plain language. Do not copy it word for word if it is \
clickbait.
- Do not write any URLs. Refer to a story by its index number.

Answer with JSON and nothing else, in this shape:

{{"intro": "one sentence on the shape of the day, no more",
  "stories": [{{"index": 1, "headline": "...", "summary": "..."}}]}}

The stories:

{candidates}
"""


def render(day: dt.date, intro: str, stories: Sequence[Story]) -> str:
    """Assemble the post from the model's words and our own links."""
    sections = "\n\n".join(
        f"## {_link(story.headline, story.entry.link)}\n\n"
        f"{story.summary}\n\n"
        f"*{story.entry.source}*"
        for story in stories
    )
    body = f"{intro}\n\n{sections}" if intro else sections
    return _document(
        day,
        description=intro or _first_headline(stories),
        body=body,
        footer="Selected and summarized automatically from the sources linked above.",
    )


def render_links(day: dt.date, entries: Sequence[Entry]) -> str:
    """The digest we publish when the model is unavailable: sources, no prose."""
    note = (
        "The summaries could not be generated today, so here is the reading list "
        "on its own."
    )
    links = "\n".join(
        f"- {_link(entry.title, entry.link)} - *{entry.source}*" for entry in entries
    )
    return _document(
        day,
        description=note,
        body=f"{note}\n\n{links}",
        footer="Selected automatically from the sources linked above.",
    )


def _document(day: dt.date, *, description: str, body: str, footer: str) -> str:
    title = f"Daily digest: {format_date(day)}"
    tags = "\n".join(f"  - {tag}" for tag in TAGS)
    return (
        "---\n"
        f"title: {_quote(title)}\n"
        f"date: {day.isoformat()}\n"
        f"description: {_quote(_shorten(description))}\n"
        "tags:\n"
        f"{tags}\n"
        "---\n"
        "\n"
        f"{body}\n"
        "\n"
        f"*{footer}*\n"
    )


def _stories(raw: object, entries: Sequence[Entry], *, limit: int) -> list[Story]:
    """Keep the items that point at a real entry and actually say something."""
    if not isinstance(raw, list):
        raise DigestError("the answer has no list of stories")

    stories: list[Story] = []
    used: set[int] = set()

    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index", 0))
        except (TypeError, ValueError):
            continue
        if not 1 <= index <= len(entries) or index in used:
            continue

        entry = entries[index - 1]
        headline = " ".join(str(item.get("headline", "") or entry.title).split())
        summary = " ".join(str(item.get("summary", "")).split())
        if not summary:
            continue

        used.add(index)
        stories.append(Story(entry=entry, headline=headline, summary=summary))
        if len(stories) == limit:
            break

    return stories


def _json(answer: str) -> dict:
    """Read the JSON out of an answer that may be wrapped in prose or fences."""
    match = _JSON_BLOCK.search(answer)
    if match is None:
        raise DigestError(f"no JSON in the answer: {answer[:200]!r}")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as error:
        raise DigestError(f"the answer is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise DigestError("the answer is not a JSON object")
    return payload


def _link(text: str, url: str) -> str:
    """A Markdown link that survives brackets in the text and spaces in the URL."""
    label = text.replace("[", "\\[").replace("]", "\\]")
    target = f"<{url}>" if re.search(r"[\s()]", url) else url
    return f"[{label}]({target})"


def _quote(value: str) -> str:
    """Quote a front matter value. Our parser has no escapes, so neither do we."""
    return '"{}"'.format(" ".join(value.split()).replace('"', "'"))


def _shorten(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= DESCRIPTION_LIMIT:
        return collapsed
    return f"{collapsed[: DESCRIPTION_LIMIT - 3].rstrip()}..."


def _first_headline(stories: Sequence[Story]) -> str:
    return stories[0].headline if stories else "Today in technology."
