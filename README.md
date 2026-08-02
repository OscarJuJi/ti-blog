# ti-blog

A personal blog with two authors: an agent that publishes a technology news
digest every morning, and me.

Live at <https://oscarjuji.github.io/ti-blog/>.

Nothing here is a framework. The static site generator in [`ssg/`](ssg/) is
written from scratch — front matter parsing, templating, RSS, sitemap — with
[mistune](https://mistune.lepture.com/) as the only dependency, because getting
Markdown right is a long tail of edge cases. The agent in [`agent/`](agent/) is
written from scratch too, over `urllib` and `xml.etree`.

## Layout

| Path | What it is |
|---|---|
| `content/posts/*.md` | Every post. The source of truth for the whole site. |
| `ssg/` | The generator: `frontmatter` → `posts` → `render` → `build`, plus `feed` and `sitemap`. |
| `agent/` | The daily digest: `feeds` → `rank` → `llm` → `digest`, driven by `run`. |
| `templates/`, `static/` | Page templates, the stylesheet, and the CMS at `static/admin/`. |
| `config.toml` | Site settings and the agent's feed list. |
| `tests/` | `pytest`. The build and the digest both have integration tests. |

## Running it locally

```bash
python -m venv .venv && .venv/Scripts/activate    # source .venv/bin/activate on Linux
pip install -r requirements.txt

python -m pytest -q                # the test suite
python -m ssg.build --serve        # build and preview on http://127.0.0.1:8000/ti-blog/
```

`--serve` answers the `/ti-blog/` prefix that the deployed pages use, so links
work locally exactly as they do in production.

## Writing a post

Either way ends up as a Markdown file in `content/posts/`, and any commit to
`main` rebuilds and redeploys the site.

**In the browser.** Go to [`/admin/`](https://oscarjuji.github.io/ti-blog/admin/)
and press *Sign In with Token*. It wants a GitHub fine-grained personal access
token with read and write access to *Contents* on this repository. Saving a post
there commits it for you.

**From the terminal.**

```bash
python scripts/new_post.py "What I learned about CUDA" --tags cuda,notes
```

Then edit the file it prints and push it.

The front matter is `title` and `date` (required), plus `description` and `tags`.
The filename may start with `YYYY-MM-DD-`; the slug is whatever follows it.

## The agent

Every morning [`daily-digest.yml`](.github/workflows/daily-digest.yml) reads the
feeds listed in `config.toml`, keeps what was published in the last day, drops
duplicates and non-English titles, and hands about twenty candidates to Gemini.

The model answers with JSON that points at candidates **by index** and never
writes a URL. Every link in the published post is copied from the feed it came
from, so a wrong summary is possible but an invented source is not.

If the model is unreachable, or too few of its picks survive validation, the
agent publishes the reading list with no prose rather than skipping the day.

```bash
python -m agent.run --dry-run --llm none      # what the feeds have, no model
python -m agent.run --dry-run --llm ollama    # draft with a local model
python -m agent.run                           # write content/posts/<date>-daily-digest.md
```

The run is idempotent: if the day's file exists it stops, unless given `--force`.

## Setting it up elsewhere

1. Point `config.toml` at your own `url` and `base_url`, and `static/admin/config.yml`
   at your own repository.
2. Repository *Settings → Pages → Source: GitHub Actions*.
3. Add a `GEMINI_API_KEY` secret ([free key from AI Studio](https://aistudio.google.com/apikey)).
   Without it the agent still runs, and still publishes links.
