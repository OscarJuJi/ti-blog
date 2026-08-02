"""A very small template engine.

Templates are plain HTML files with two kinds of placeholder::

    {{ title }}           the value, HTML-escaped
    {{ content | safe }}  the value as-is, for HTML built elsewhere

That is the whole language. Loops and conditionals live in Python, where they
are easier to test: the caller renders a fragment per item and passes the joined
result through a ``| safe`` placeholder.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Mapping

_PLACEHOLDER = re.compile(
    r"\{\{\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<raw>\|\s*safe\s*)?\}\}"
)


class TemplateError(ValueError):
    """Raised when a template refers to something the context does not hold."""


def escape(value: object) -> str:
    """Escape *value* for inclusion in HTML or XML text."""
    return html.escape(str(value), quote=True)


def render(template: str, context: Mapping[str, object]) -> str:
    """Fill in every placeholder of *template*."""

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in context:
            raise TemplateError(f"no value for {{{{ {name} }}}}")
        value = context[name]
        return str(value) if match.group("raw") else escape(value)

    return _PLACEHOLDER.sub(replace, template)


class Templates:
    """Templates loaded from a directory, read once each."""

    def __init__(self, directory: Path):
        self._directory = Path(directory)
        self._cache: dict[str, str] = {}

    def source(self, name: str) -> str:
        if name not in self._cache:
            path = self._directory / name
            if not path.is_file():
                raise TemplateError(f"no such template: {path}")
            self._cache[name] = path.read_text(encoding="utf-8")
        return self._cache[name]

    def render(self, name: str, context: Mapping[str, object]) -> str:
        return render(self.source(name), context)
