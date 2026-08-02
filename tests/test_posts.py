import datetime as dt

import pytest

from ssg import posts


def write(directory, name, text):
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_a_post(tmp_path):
    path = write(
        tmp_path,
        "2026-08-01-hello-world.md",
        "---\ntitle: Hello world\ndate: 2026-08-01\ndescription: A greeting.\n"
        "tags: [meta, notes]\n---\n\nThe body.\n",
    )

    post = posts.load(path)

    assert post.slug == "hello-world"
    assert post.title == "Hello world"
    assert post.date == dt.date(2026, 8, 1)
    assert post.description == "A greeting."
    assert post.tags == ("meta", "notes")
    assert post.body == "The body."
    assert post.path == "posts/hello-world/"
    assert post.display_date == "August 1, 2026"


def test_accepts_the_iso_timestamp_the_cms_writes(tmp_path):
    path = write(
        tmp_path, "note.md", "---\ntitle: T\ndate: 2026-08-01T13:00:00.000Z\n---\n\nBody.\n"
    )
    assert posts.load(path).date == dt.date(2026, 8, 1)


def test_a_single_tag_becomes_a_one_item_tuple(tmp_path):
    path = write(tmp_path, "note.md", "---\ntitle: T\ndate: 2026-08-01\ntags: python\n---\n\nB.\n")
    assert posts.load(path).tags == ("python",)


def test_missing_tags_and_description_are_empty(tmp_path):
    path = write(tmp_path, "note.md", "---\ntitle: T\ndate: 2026-08-01\n---\n\nBody.\n")
    post = posts.load(path)
    assert post.tags == ()
    assert post.description == ""


def test_rejects_a_post_without_a_title(tmp_path):
    path = write(tmp_path, "note.md", "---\ndate: 2026-08-01\n---\n\nBody.\n")
    with pytest.raises(posts.PostError, match="missing metadata: title"):
        posts.load(path)


def test_rejects_an_unreadable_date(tmp_path):
    path = write(tmp_path, "note.md", "---\ntitle: T\ndate: yesterday\n---\n\nBody.\n")
    with pytest.raises(posts.PostError, match="invalid date"):
        posts.load(path)


def test_rejects_an_empty_body(tmp_path):
    path = write(tmp_path, "note.md", "---\ntitle: T\ndate: 2026-08-01\n---\n\n\n")
    with pytest.raises(posts.PostError, match="body is empty"):
        posts.load(path)


def test_load_all_returns_newest_first(tmp_path):
    write(tmp_path, "2026-07-30-older.md", "---\ntitle: Older\ndate: 2026-07-30\n---\n\nB.\n")
    write(tmp_path, "2026-08-01-newer.md", "---\ntitle: Newer\ndate: 2026-08-01\n---\n\nB.\n")

    assert [post.slug for post in posts.load_all(tmp_path)] == ["newer", "older"]


def test_load_all_rejects_two_files_with_the_same_slug(tmp_path):
    write(tmp_path, "2026-07-30-note.md", "---\ntitle: A\ndate: 2026-07-30\n---\n\nB.\n")
    write(tmp_path, "2026-08-01-note.md", "---\ntitle: B\ndate: 2026-08-01\n---\n\nB.\n")

    with pytest.raises(posts.PostError, match="already used by"):
        posts.load_all(tmp_path)


def test_load_all_on_an_empty_directory(tmp_path):
    assert posts.load_all(tmp_path) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello World", "hello-world"),
        ("  Spaces  and---dashes ", "spaces-and-dashes"),
        ("Qué pasó en TI", "que-paso-en-ti"),
        ("C# & .NET 10!", "c-net-10"),
    ],
)
def test_slugify(text, expected):
    assert posts.slugify(text) == expected
