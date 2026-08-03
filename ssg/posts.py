"""Loading post files into the objects the rest of the generator works with."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ssg import frontmatter

REQUIRED_KEYS = ("title", "date")

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


class PostError(ValueError):
    """Raised when a post file cannot be turned into a :class:`Post`."""


@dataclass(frozen=True)
class Post:
    """One post, ready to render."""

    slug: str
    title: str
    date: dt.date
    description: str
    tags: tuple[str, ...]
    body: str
    source: Path

    @property
    def path(self) -> str:
        """Where the page lands in the output tree, relative to the site root."""
        return f"posts/{self.slug}/"

    @property
    def display_date(self) -> str:
        """The date as read by a person, e.g. ``August 1, 2026``."""
        return format_date(self.date)

    @property
    def summary(self) -> str:
        """The description, or the first real paragraph when there is none.

        Headings are skipped: a preview reading "Today's stories" helps nobody.
        """
        if self.description:
            return self.description
        blocks = (block.strip() for block in self.body.split("\n\n"))
        opening = next(
            (block for block in blocks if block and not block.startswith("#")), ""
        )
        text = " ".join(opening.lstrip("> ").split())
        return text if len(text) <= 200 else f"{text[:197].rstrip()}..."


def load(path: Path) -> Post:
    """Read a single post file."""
    path = Path(path)
    try:
        metadata, body = frontmatter.split(path.read_text(encoding="utf-8"))
    except frontmatter.FrontmatterError as error:
        raise PostError(f"{path.name}: {error}") from error

    missing = [key for key in REQUIRED_KEYS if not metadata.get(key)]
    if missing:
        raise PostError(f"{path.name}: missing metadata: {', '.join(missing)}")
    if not body.strip():
        raise PostError(f"{path.name}: the body is empty")

    return Post(
        slug=slug_for(path),
        title=str(metadata["title"]),
        date=parse_date(metadata["date"], source=path.name),
        description=str(metadata.get("description") or ""),
        tags=_tags(metadata.get("tags")),
        body=body,
        source=path,
    )


def load_all(directory: Path) -> list[Post]:
    """Read every post in *directory*, newest first."""
    posts = [load(path) for path in sorted(Path(directory).glob("*.md"))]

    seen: dict[str, Path] = {}
    for post in posts:
        if post.slug in seen:
            raise PostError(
                f"{post.source.name}: slug {post.slug!r} is already used by {seen[post.slug].name}"
            )
        seen[post.slug] = post.source

    posts.sort(key=lambda post: (post.date, post.slug), reverse=True)
    return posts


def format_date(date: dt.date) -> str:
    """Write a date the way a reader says it, in English whatever the locale."""
    return f"{_MONTHS[date.month - 1]} {date.day}, {date.year}"


def parse_date(raw: object, *, source: str) -> dt.date:
    """Read a date, accepting the full ISO timestamps the CMS writes."""
    text = str(raw).strip()
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError as error:
        raise PostError(f"{source}: invalid date {raw!r}, expected YYYY-MM-DD") from error


def slug_for(path: Path) -> str:
    """Derive a slug from a filename.

    The whole stem is kept, date prefix included. Dropping the date reads better
    but collides: every daily digest is called ``daily-digest``, so the second
    one would fight the first for the same URL.
    """
    slug = slugify(Path(path).stem)
    if not slug:
        raise PostError(f"{Path(path).name}: filename yields an empty slug")
    return slug


def slugify(text: str) -> str:
    """Reduce *text* to lowercase ASCII words joined by hyphens."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _tags(value: object) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(tag) for tag in value if str(tag).strip())
