---
title: How this blog works
date: 2026-08-01
description: A static site generator written from scratch, and an agent that publishes a news digest here every morning.
tags:
  - meta
  - python
---

This site has two authors. Most mornings the post you find here was assembled by
an agent that reads a handful of technology feeds and writes up what happened.
Everything else is written by me.

## The generator

There is no framework underneath. A small Python package turns the Markdown
files in `content/posts/` into the pages you are reading:

- `frontmatter.py` reads the metadata block that opens every post.
- `posts.py` turns those files into objects: slug, date, tags, body.
- `render.py` is a template engine with exactly two features, placeholder
  substitution and an escape hatch for HTML built elsewhere.
- `feed.py` and `sitemap.py` write the RSS feed and the sitemap by hand.
- `build.py` puts it together and drops the result in `_site/`.

The one dependency is [mistune](https://mistune.lepture.com/), which converts
Markdown to HTML. Getting Markdown right is a long tail of edge cases, and the
posts have to render correctly whether I wrote them or the agent did.

## The agent

Every morning a scheduled job fetches the feeds listed in `config.toml`, keeps
the entries published in the last day, drops duplicates, and hands the survivors
to a language model with one instruction: summarize these, link to the sources,
skip anything that is only marketing.

The result is committed to this repository as an ordinary Markdown file, which
triggers a rebuild. If the model is unavailable the agent still publishes a plain
list of links, because a thin digest is better than a missing day.

Two things follow from that design. The summaries are the model's reading of a
headline, not mine, so the link to the original always matters more than the
paragraph next to it. And because every post is a file in a git repository, the
history of what was published, and any correction to it, is public.

## Writing here myself

My own posts are Markdown files in the same folder, committed the same way.
Nothing about the daily digest gets in the way of writing a longer piece when
there is something worth saying.
