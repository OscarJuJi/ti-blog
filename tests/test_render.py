import pytest

from ssg import render


def test_substitutes_and_escapes():
    assert render.render("<h1>{{ title }}</h1>", {"title": "Tom & Jerry"}) == (
        "<h1>Tom &amp; Jerry</h1>"
    )


def test_safe_filter_inserts_html_as_is():
    assert render.render("{{ body | safe }}", {"body": "<p>Hi</p>"}) == "<p>Hi</p>"


def test_tolerates_spacing_inside_the_braces():
    assert render.render("{{title}} {{  title  }}", {"title": "x"}) == "x x"


def test_a_missing_value_is_an_error():
    with pytest.raises(render.TemplateError, match="no value for"):
        render.render("{{ nope }}", {})


def test_templates_are_read_from_disk_and_cached(tmp_path):
    (tmp_path / "page.html").write_text("<p>{{ text }}</p>", encoding="utf-8")
    templates = render.Templates(tmp_path)

    assert templates.render("page.html", {"text": "one"}) == "<p>one</p>"

    (tmp_path / "page.html").write_text("changed", encoding="utf-8")
    assert templates.render("page.html", {"text": "two"}) == "<p>two</p>"


def test_a_missing_template_is_an_error(tmp_path):
    with pytest.raises(render.TemplateError, match="no such template"):
        render.Templates(tmp_path).render("absent.html", {})
