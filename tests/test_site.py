import pytest

from ssg import site as site_module
from ssg.site import Site


def make(base_url="/ti-blog"):
    return Site.from_config(
        {"site": {"title": "T", "url": "https://oscarjuji.github.io", "base_url": base_url}}
    )


def test_paths_carry_the_project_prefix():
    site = make()
    assert site.path() == "/ti-blog/"
    assert site.path("posts/hello/") == "/ti-blog/posts/hello/"
    assert site.absolute("feed.xml") == "https://oscarjuji.github.io/ti-blog/feed.xml"


def test_a_root_site_needs_no_prefix():
    site = make(base_url="")
    assert site.path() == "/"
    assert site.absolute("feed.xml") == "https://oscarjuji.github.io/feed.xml"


@pytest.mark.parametrize("written", ["ti-blog", "/ti-blog", "/ti-blog/", "ti-blog/"])
def test_the_prefix_is_normalized_however_it_is_written(written):
    assert make(base_url=written).base_url == "/ti-blog"


def test_a_trailing_slash_on_the_origin_is_dropped():
    site = Site.from_config({"site": {"url": "https://example.com/", "base_url": ""}})
    assert site.absolute() == "https://example.com/"


def test_the_real_config_file_loads():
    site = Site.load()
    assert site.title
    assert site.url.startswith("https://")
    assert site.base_url in ("", "/ti-blog")

    config = site_module.load_config()
    assert config["agent"]["feeds"], "the agent needs at least one feed"
