"""The daily run: read the feeds, write the post, leave the commit to git.

    python -m agent.run --dry-run          see today's digest without writing it
    python -m agent.run --llm ollama       draft it with a local model
    python -m agent.run                    write it into content/posts/
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import zoneinfo
from pathlib import Path
from typing import Any, Sequence

from agent import digest, feeds, rank
from agent.llm import LLM, LLMError, from_environment
from ssg.site import ROOT, load_config

POSTS = ROOT / "content" / "posts"
SLUG = "daily-digest"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    config = load_config()
    settings: dict[str, Any] = config.get("agent", {})

    now = dt.datetime.now(dt.timezone.utc)
    day = args.date or now.astimezone(_zone(config["site"].get("timezone", "UTC"))).date()
    target = args.output_dir / f"{day.isoformat()}-{SLUG}.md"

    if target.exists() and not args.force:
        print(f"{target.name} is already written; nothing to do")
        return 0

    entries = feeds.collect(settings.get("feeds", []), on_error=_warn)
    print(f"read {len(entries)} entries from {len(settings.get('feeds', []))} feeds")
    if not entries:
        _warn("every feed failed; leaving today alone")
        return 1

    shortlist = rank.select(
        entries,
        now=now,
        window_hours=settings.get("window_hours", 26),
        per_feed_limit=settings.get("per_feed_limit", 6),
        candidate_limit=settings.get("candidate_limit", 20),
    )
    print(f"shortlisted {len(shortlist)} of them")
    if not shortlist:
        _warn("nothing published recently enough to write about")
        return 1

    document = digest.build(
        day,
        shortlist,
        llm=_model(args, settings),
        min_stories=settings.get("min_stories", 5),
        max_stories=settings.get("max_stories", 10),
        on_error=_warn,
    )

    if args.dry_run:
        print("\n--- would write " + target.name + " ---\n")
        print(document)
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8", newline="\n")
    print(f"wrote {target}")
    return 0


def _model(args: argparse.Namespace, settings: dict[str, Any]) -> LLM | None:
    """The backend to draft with, or None to publish a plain list of links."""
    if args.llm == "none":
        return None
    try:
        model = from_environment(
            backend=args.llm,
            model=settings.get("model", ""),
            ollama_model=args.ollama_model,
        )
    except LLMError as error:
        _warn(f"no model available ({error}); the digest will be links only")
        return None
    print(f"drafting with {model.name}")
    return model


def _zone(name: str) -> dt.tzinfo:
    try:
        return zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError) as error:
        _warn(f"unknown timezone {name!r} ({error}); dating the post in UTC")
        return dt.timezone.utc


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the daily digest.")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the post instead of writing it"
    )
    parser.add_argument(
        "--llm",
        choices=("auto", "gemini", "ollama", "none"),
        default="auto",
        help="which backend to draft with (default: Gemini if a key is set, else Ollama)",
    )
    parser.add_argument(
        "--ollama-model", default=DEFAULT_OLLAMA_MODEL, help="model to ask Ollama for"
    )
    parser.add_argument(
        "--date",
        type=dt.date.fromisoformat,
        help="write the digest for this day instead of today",
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite the day's digest if it exists"
    )
    parser.add_argument("--output-dir", type=Path, default=POSTS)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
