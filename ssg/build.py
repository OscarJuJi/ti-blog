"""The build: content and templates in, a deployable ``_site/`` out.

Run it with ``python -m ssg.build`` (add ``--serve`` to preview the result).
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Sequence

from ssg import feed, markdown, sitemap
from ssg.posts import Post, load_all
from ssg.render import Templates, escape
from ssg.site import ROOT, Site, load_config

OUTPUT = ROOT / "_site"

# Written at the root of every build. It also tells GitHub Pages not to run the
# output through Jekyll, and it is how :func:`_reset` recognises its own work.
MARKER = ".nojekyll"


class BuildError(RuntimeError):
    """Raised when the build cannot safely proceed."""


def build(
    *,
    root: Path = ROOT,
    output: Path = OUTPUT,
    now: dt.datetime | None = None,
) -> list[Post]:
    """Render the whole site and return the posts that went into it."""
    root, output = Path(root), Path(output)
    now = now or dt.datetime.now(dt.timezone.utc)

    site = Site.from_config(load_config(root / "config.toml"))
    templates = Templates(root / "templates")
    all_posts = load_all(root / "content" / "posts")

    _reset(output)
    shutil.copytree(root / "static", output, dirs_exist_ok=True)

    chrome = {
        "lang": site.language,
        "site_title": site.title,
        "tagline": site.tagline,
        "home_url": site.path(),
        "style_url": site.path("style.css"),
        "feed_url": site.path(feed.FEED_PATH),
        "admin_url": site.path("admin/"),
        "author": site.author,
        "year": now.year,
    }

    _write(output / "index.html", _index(site, templates, chrome, all_posts))
    for post in all_posts:
        _write(output / post.path / "index.html", _post(site, templates, chrome, post))
    _write(output / "404.html", _not_found(site, templates, chrome))

    _write(output / feed.FEED_PATH, feed.build(site, all_posts, built_at=now))
    _write(output / sitemap.SITEMAP_PATH, sitemap.build(site, all_posts))
    _write(output / MARKER, "")

    return all_posts


def _index(site: Site, templates: Templates, chrome: dict, all_posts: Sequence[Post]) -> str:
    if all_posts:
        items = "\n".join(
            templates.render(
                "post_item.html",
                {
                    "url": site.path(post.path),
                    "title": post.title,
                    "iso_date": post.date.isoformat(),
                    "display_date": post.display_date,
                    "summary": post.summary,
                    "tags": _tags(post.tags),
                },
            )
            for post in all_posts
        )
    else:
        items = '<p class="empty">Nothing published yet.</p>'

    content = templates.render("index.html", {"posts": items})
    return _page(
        templates,
        chrome,
        content=content,
        page_title=site.title,
        description=site.description,
        canonical=site.absolute(),
    )


def _post(site: Site, templates: Templates, chrome: dict, post: Post) -> str:
    content = templates.render(
        "post.html",
        {
            "title": post.title,
            "iso_date": post.date.isoformat(),
            "display_date": post.display_date,
            "tags": _tags(post.tags),
            "body": markdown.to_html(post.body),
            "home_url": chrome["home_url"],
        },
    )
    return _page(
        templates,
        chrome,
        content=content,
        page_title=f"{post.title} - {site.title}",
        description=post.summary,
        canonical=site.absolute(post.path),
    )


def _not_found(site: Site, templates: Templates, chrome: dict) -> str:
    content = templates.render("404.html", {"home_url": chrome["home_url"]})
    return _page(
        templates,
        chrome,
        content=content,
        page_title=f"Page not found - {site.title}",
        description="",
        canonical=site.absolute("404.html"),
    )


def _page(templates: Templates, chrome: dict, **page: object) -> str:
    return templates.render("base.html", {**chrome, **page})


def _tags(tags: Sequence[str]) -> str:
    if not tags:
        return ""
    items = "".join(f"<li>{escape(tag)}</li>" for tag in tags)
    return f'<ul class="tags">{items}</ul>'


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _reset(output: Path) -> None:
    """Empty the output directory, refusing to erase anything we did not build."""
    if output.exists():
        if any(output.iterdir()) and not (output / MARKER).exists():
            raise BuildError(
                f"{output} is not empty and does not look like a build of this site; "
                "refusing to erase it"
            )
        shutil.rmtree(output)
    output.mkdir(parents=True)


def serve(directory: Path, base_url: str, port: int = 8000) -> None:
    """Preview a build, answering the prefixed URLs the pages actually use."""

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def translate_path(self, path: str) -> str:
            if base_url and (path == base_url or path.startswith(f"{base_url}/")):
                path = path[len(base_url) :] or "/"
            return super().translate_path(path)

        def log_message(self, *args):  # quieter than the default one-line-per-asset
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"serving {directory} at http://127.0.0.1:{port}{base_url}/  (ctrl-c to stop)")
        server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the blog into _site/.")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="where to write the site")
    parser.add_argument("--serve", action="store_true", help="preview the result over HTTP")
    parser.add_argument("--port", type=int, default=8000, help="port used by --serve")
    args = parser.parse_args(argv)

    built = build(output=args.output)
    print(f"built {len(built)} post(s) into {args.output}")

    if args.serve:
        serve(args.output, Site.load().base_url, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
