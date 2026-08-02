# Design

Why the pieces are shaped the way they are. The README says how to use them.

## The generator is written by hand

The point of this blog is partly the blog and partly the building of it, so
everything that could reasonably be written from scratch was: the front matter
parser, the template engine, the RSS feed, the sitemap.

The exception is Markdown. Both the CMS and the agent emit ordinary Markdown, and
a hand-rolled subset parser would render some of it wrong — tables one day,
nested lists the next. `mistune` is small, pure Python, and removes that whole
class of failure. It is the only runtime dependency.

The front matter parser accepts a deliberately small subset of YAML: scalars,
flow lists, block lists. That is everything this blog writes. A small grammar
means a malformed post fails loudly at build time instead of rendering strangely.

The template engine has two features, `{{ value }}` and `{{ value | safe }}`, and
raises on an unknown name. Loops live in Python, where they are easy to test: the
build renders a fragment per post and passes the joined string through `| safe`.
A missing value is an error rather than an empty string, because a silently blank
page is the failure that is hardest to notice.

## Links are ours, prose is the model's

The agent hands the model a numbered list of candidates and asks for JSON that
refers to them **by index**. The model is told not to write URLs, and its answer
is validated: an index outside the list is dropped, a repeated index is dropped,
a story with no summary is dropped.

The published Markdown is then assembled from our own data. Every link is copied
from the feed entry it belongs to. The consequence is worth stating plainly: the
model can summarize a story badly, but it cannot invent a source, and it cannot
attach a real headline to a URL that does not exist.

The site says out loud that the digests are machine-written, and each one ends
with a line saying so.

## Failure is expected, not exceptional

A feed being down, a rate limit, a model returning prose instead of JSON: each of
these happens eventually, and none should cost a day of publishing.

- `feeds.collect` reports a dead source and carries on with the rest.
- `llm._post` retries the status codes that pass on their own (429, 5xx) and
  fails fast on the ones that do not (400).
- `digest.build` falls back to a plain reading list when the model is unreachable
  or its answer does not validate.

The one thing the agent will not do is publish an empty post: with no entries at
all it exits non-zero and leaves the day alone.

## Deploying

GitHub Pages serves this as a *project* site, so every internal URL carries the
`/ti-blog` prefix. `Site.path()` is the only place that knows it, and
`build --serve` reproduces the prefix locally so a link that works in preview
works in production.

The two workflows exist separately because of one GitHub rule: **a push made with
`GITHUB_TOKEN` does not trigger `on: push`**. If the agent simply committed, the
site would never rebuild. So `daily-digest.yml` commits and then calls
`build-deploy.yml` through `workflow_call`, and skips the call when there was
nothing new to commit.

The build runs the test suite before it renders anything. A broken post or a
broken parser fails the deploy instead of publishing a broken page.

## What was left out

No tags pages, no pagination, no search, no analytics, no comments. Each is easy
to add to a generator this size once there is a reason to; none of them earns its
place on a blog with one author and a daily digest.
