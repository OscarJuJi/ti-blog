"""Start a post from the command line.

    python scripts/new_post.py "What I learned about CUDA" --tags cuda,notes
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ssg.posts import slugify  # noqa: E402  (needs the path above)

POSTS = Path(__file__).resolve().parent.parent / "content" / "posts"

TEMPLATE = """---
title: "{title}"
date: {date}
description: ""
tags:
{tags}
---

Write here.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an empty post.")
    parser.add_argument("title")
    parser.add_argument("--tags", default="", help="comma separated")
    parser.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument("--posts-dir", type=Path, default=POSTS)
    args = parser.parse_args(argv)

    slug = slugify(args.title)
    if not slug:
        print("that title yields an empty slug", file=sys.stderr)
        return 1

    path = args.posts_dir / f"{args.date.isoformat()}-{slug}.md"
    if path.exists():
        print(f"{path} already exists", file=sys.stderr)
        return 1

    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        TEMPLATE.format(
            title=args.title.replace('"', "'"),
            date=args.date.isoformat(),
            tags="\n".join(f"  - {tag}" for tag in tags) or "  - notes",
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
