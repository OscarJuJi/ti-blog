"""The site-wide settings read from ``config.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.toml"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Read the TOML configuration shared by the generator and the agent."""
    with open(path, "rb") as handle:
        return tomllib.load(handle)


@dataclass(frozen=True)
class Site:
    """Everything the templates need to know about the site itself."""

    title: str
    tagline: str
    description: str
    author: str
    url: str
    base_url: str
    language: str
    timezone: str

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "Site":
        section = config.get("site", {})
        return cls(
            title=section.get("title", "Blog"),
            tagline=section.get("tagline", ""),
            description=section.get("description", ""),
            author=section.get("author", ""),
            url=section.get("url", "").rstrip("/"),
            base_url=_normalize_base(section.get("base_url", "")),
            language=section.get("language", "en"),
            timezone=section.get("timezone", "UTC"),
        )

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Site":
        return cls.from_config(load_config(path))

    def path(self, relative: str = "") -> str:
        """Turn a site-relative path into a root-relative URL, with the prefix."""
        return f"{self.base_url}/{relative.lstrip('/')}"

    def absolute(self, relative: str = "") -> str:
        """Same as :meth:`path`, but including the origin. Used by the feed."""
        return f"{self.url}{self.path(relative)}"


def _normalize_base(value: str) -> str:
    """Accept ``ti-blog``, ``/ti-blog`` or ``/ti-blog/`` and settle on ``/ti-blog``."""
    trimmed = value.strip().strip("/")
    return f"/{trimmed}" if trimmed else ""
