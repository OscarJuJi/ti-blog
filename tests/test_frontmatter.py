import pytest

from ssg import frontmatter


def test_reads_scalars_and_body():
    metadata, body = frontmatter.split(
        "---\ntitle: Hello world\ndate: 2026-08-01\n---\n\nThe body.\n"
    )
    assert metadata == {"title": "Hello world", "date": "2026-08-01"}
    assert body == "The body."


def test_strips_one_layer_of_quotes():
    metadata, _ = frontmatter.split("---\ntitle: \"Quoted: it works\"\n---\n")
    assert metadata["title"] == "Quoted: it works"


def test_keeps_a_hash_inside_a_value():
    metadata, _ = frontmatter.split("---\ntitle: C# in 2026\n---\n")
    assert metadata["title"] == "C# in 2026"


def test_reads_a_flow_list():
    metadata, _ = frontmatter.split("---\ntags: [python, web dev, ai]\n---\n")
    assert metadata["tags"] == ["python", "web dev", "ai"]


def test_reads_an_indented_block_list():
    metadata, _ = frontmatter.split("---\ntags:\n  - python\n  - notes\ntitle: T\n---\n")
    assert metadata["tags"] == ["python", "notes"]
    assert metadata["title"] == "T"


def test_an_empty_value_is_an_empty_string():
    metadata, _ = frontmatter.split("---\ntitle: T\ndescription:\n---\n")
    assert metadata["description"] == ""


def test_ignores_comment_lines():
    metadata, _ = frontmatter.split("---\n# a comment\ntitle: T\n---\n")
    assert metadata == {"title": "T"}


def test_handles_windows_line_endings():
    metadata, body = frontmatter.split("---\r\ntitle: T\r\n---\r\n\r\nBody line.\r\n")
    assert metadata == {"title": "T"}
    assert body == "Body line."


def test_a_horizontal_rule_in_the_body_is_left_alone():
    _, body = frontmatter.split("---\ntitle: T\n---\n\nBefore.\n\n---\n\nAfter.\n")
    assert body == "Before.\n\n---\n\nAfter."


def test_rejects_a_document_without_a_block():
    with pytest.raises(frontmatter.FrontmatterError, match="does not open"):
        frontmatter.split("Just a body.\n")


def test_rejects_an_unclosed_block():
    with pytest.raises(frontmatter.FrontmatterError, match="never closed"):
        frontmatter.split("---\ntitle: T\n\nBody.\n")


def test_rejects_a_duplicate_key():
    with pytest.raises(frontmatter.FrontmatterError, match="duplicate key"):
        frontmatter.split("---\ntitle: One\ntitle: Two\n---\n")


def test_rejects_a_line_that_is_not_a_pair():
    with pytest.raises(frontmatter.FrontmatterError, match="not a 'key: value' pair"):
        frontmatter.split("---\ntitle: T\nnonsense\n---\n")
