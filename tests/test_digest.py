import datetime as dt
import json

import pytest

from agent import digest
from agent.feeds import Entry
from agent.llm import LLMError
from ssg import posts

DAY = dt.date(2026, 8, 1)

ENTRIES = [
    Entry(
        title="Rust 2.0 ships",
        link="https://example.com/rust-2",
        summary="The release lands today.",
        published=None,
        source="Ars Technica",
    ),
    Entry(
        title="A database rewrite",
        link="https://example.com/db?utm_source=rss",
        summary="",
        published=None,
        source="Hacker News",
    ),
    Entry(
        title="Third story",
        link="https://example.com/third",
        summary="",
        published=None,
        source="The Verge",
    ),
    Entry(
        title="Fourth story",
        link="https://example.com/fourth",
        summary="",
        published=None,
        source="dev.to",
    ),
]


class FakeLLM:
    """Answers with whatever the test decided, and remembers what it was asked."""

    name = "fake"

    def __init__(self, answer):
        self.answer = answer
        self.prompt = None
        self.system = None

    def generate(self, prompt, *, system=""):
        self.prompt, self.system = prompt, system
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def answer(*indices, intro="A quiet day."):
    return json.dumps(
        {
            "intro": intro,
            "stories": [
                {
                    "index": index,
                    "headline": f"Headline {index}",
                    "summary": f"Summary of story {index}.",
                }
                for index in indices
            ],
        }
    )


def test_the_post_it_writes_is_a_post_the_generator_can_load(tmp_path):
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(answer(1, 2, 3)))

    path = tmp_path / "2026-08-01-daily-digest.md"
    path.write_text(document, encoding="utf-8")
    post = posts.load(path)

    assert post.title == "Daily digest: August 1, 2026"
    assert post.date == DAY
    assert post.tags == ("digest", "news")
    assert post.description == "A quiet day."
    assert post.slug == "2026-08-01-daily-digest"


def test_links_come_from_the_feeds_not_from_the_model():
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(answer(1, 2, 3)))

    assert "(https://example.com/rust-2)" in document
    assert "## [Headline 1](https://example.com/rust-2)" in document
    assert "*Ars Technica*" in document


def test_a_story_pointing_at_no_entry_is_dropped():
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(answer(1, 99, 2, 3)))

    assert document.count("## [") == 3
    assert "Headline 99" not in document


def test_the_same_entry_twice_is_only_published_once():
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(answer(1, 1, 2, 3)))
    assert document.count("## [") == 3


def test_json_wrapped_in_a_code_fence_is_still_read():
    fenced = f"Here you go:\n\n```json\n{answer(1, 2, 3)}\n```\n"
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(fenced))
    assert "Headline 1" in document


def test_more_stories_than_asked_for_are_cut():
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(answer(1, 2, 3, 4)), max_stories=2)
    assert document.count("## [") == 2


def test_falls_back_to_links_when_the_model_is_unreachable():
    problems = []
    document = digest.build(
        DAY, ENTRIES, llm=FakeLLM(LLMError("503")), on_error=problems.append
    )

    assert "summaries could not be generated" in document
    assert "- [Rust 2.0 ships](https://example.com/rust-2)" in document
    assert problems and "503" in problems[0]


def test_falls_back_when_too_few_stories_survive():
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(answer(1)), on_error=lambda _: None)
    assert "summaries could not be generated" in document


def test_falls_back_when_the_answer_is_not_json():
    document = digest.build(
        DAY, ENTRIES, llm=FakeLLM("I would rather not."), on_error=lambda _: None
    )
    assert "summaries could not be generated" in document


def test_the_links_only_post_also_loads(tmp_path):
    path = tmp_path / "2026-08-01-daily-digest.md"
    path.write_text(digest.render_links(DAY, ENTRIES), encoding="utf-8")
    assert posts.load(path).tags == ("digest", "news")


def test_quotes_in_a_summary_cannot_break_the_front_matter(tmp_path):
    reply = json.dumps(
        {
            "intro": 'He said "hello"\nand left',
            "stories": [
                {"index": index, "headline": f"H{index}", "summary": "S."}
                for index in (1, 2, 3)
            ],
        }
    )
    path = tmp_path / "2026-08-01-daily-digest.md"
    path.write_text(digest.build(DAY, ENTRIES, llm=FakeLLM(reply)), encoding="utf-8")

    assert posts.load(path).description == "He said 'hello' and left"


def test_brackets_in_a_headline_do_not_break_the_link():
    reply = json.dumps(
        {
            "intro": "",
            "stories": [
                {"index": 1, "headline": "A [bracketed] headline", "summary": "S."},
                {"index": 2, "headline": "H2", "summary": "S."},
                {"index": 3, "headline": "H3", "summary": "S."},
            ],
        }
    )
    document = digest.build(DAY, ENTRIES, llm=FakeLLM(reply))
    assert "## [A \\[bracketed\\] headline](https://example.com/rust-2)" in document


def test_without_a_model_it_publishes_the_links():
    document = digest.build(DAY, ENTRIES, llm=None)
    assert "summaries could not be generated" in document


def test_the_footer_does_not_claim_summaries_nobody_wrote():
    written = digest.build(DAY, ENTRIES, llm=FakeLLM(answer(1, 2, 3)))
    links_only = digest.build(DAY, ENTRIES, llm=None)

    assert written.rstrip().endswith("*Selected and summarized automatically from the sources linked above.*")
    assert links_only.rstrip().endswith("*Selected automatically from the sources linked above.*")


def test_no_entries_is_an_error():
    with pytest.raises(digest.DigestError, match="no entries"):
        digest.build(DAY, [], llm=None)


def test_the_prompt_carries_every_candidate_and_forbids_urls():
    model = FakeLLM(answer(1, 2, 3))
    digest.build(DAY, ENTRIES, llm=model, min_stories=5, max_stories=10)

    assert "[1] Rust 2.0 ships" in model.prompt
    assert "[4] Fourth story" in model.prompt
    assert "Do not write any URLs" in model.prompt
    assert "5 to 10" in model.prompt
    assert model.system == digest.SYSTEM
