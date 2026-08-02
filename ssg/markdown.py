"""Markdown to HTML.

The one piece of the generator that is not written here: getting Markdown right
is a long tail of edge cases, and both the CMS and the agent emit ordinary
Markdown that has to render correctly.

Raw HTML in a post is passed through rather than escaped. Posts only ever reach
the site as commits to this repository, so their authors are already trusted.
"""

from __future__ import annotations

import mistune

_render = mistune.create_markdown(
    escape=False,
    plugins=["strikethrough", "table", "url", "footnotes"],
)


def to_html(text: str) -> str:
    """Render a Markdown document."""
    return _render(text).strip()
