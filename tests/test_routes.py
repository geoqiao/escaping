from __future__ import annotations

import pytest

from escaping.routes import RouteCollisionError, RouteRegistry


def test_registry_covers_routes_and_output_mapping() -> None:
    registry = RouteRegistry("https://geoqiao.me/")
    home = registry.home()
    blog = registry.blog_archive(2)
    detail = registry.blog_detail("my-post")
    idea = registry.idea(42)
    about = registry.about()
    projects = registry.projects()
    tags = registry.tags()
    tag = registry.tag("python")
    atom = registry.atom()
    sitemap = registry.sitemap()
    robots = registry.robots()

    assert home.canonical_path == "/" and home.output_path == "index.html"
    assert blog.canonical_path == "/blog/page/2/"
    assert blog.output_path == "blog/page/2/index.html"
    assert detail.canonical_path == "/blog/my-post/"
    assert idea.output_path == "ideas/42/index.html"
    assert about.output_path == "about/index.html"
    assert projects.canonical_path == "/projects/"
    assert tags.canonical_path == "/tags/"
    assert tag.canonical_url == "https://geoqiao.me/tags/python/"
    assert atom.output_path == "atom.xml"
    assert sitemap.output_path == "sitemap.xml"
    assert robots.output_path == "robots.txt"
    assert detail.canonical_url == "https://geoqiao.me/blog/my-post/"


def test_registry_normalizes_nfc_casefold_and_rejects_collisions() -> None:
    registry = RouteRegistry("https://geoqiao.me")
    registry.register("one", "/café/", "one/index.html")
    with pytest.raises(RouteCollisionError):
        registry.register("two", "/cafe\u0301/", "two/index.html")
    with pytest.raises(RouteCollisionError):
        registry.register("three", "/CAFÉ/", "three/index.html")


def test_registry_rejects_reserved_and_malformed_dynamic_routes() -> None:
    registry = RouteRegistry("https://geoqiao.me")
    registry.blog_archive(2)
    with pytest.raises(RouteCollisionError, match="reserved"):
        registry.blog_detail("page")
    with pytest.raises(RouteCollisionError):
        registry.tag("Bad_Tag")
    with pytest.raises(RouteCollisionError):
        registry.register("bad", "relative", "bad/index.html")
    with pytest.raises(RouteCollisionError):
        registry.register("old", "/old/", "old.html")


def test_lookup_requires_emitted_path_case_without_weakening_collisions() -> None:
    registry = RouteRegistry("https://example.com")
    blog = registry.blog_archive()
    assert registry.route_for_path("/blog/") is blog
    assert registry.route_for_path("/%62log/") is blog  # same URL per RFC 3986
    assert registry.route_for_url("https://example.com/blog/") is blog
    for path in ("/Blog/", "/BLOG/", "/%42log/", "/blog"):
        assert registry.route_for_path(path) is None
        assert registry.route_for_url(f"https://example.com{path}") is None
    for output in ("other/index.html", blog.output_path):
        with pytest.raises(RouteCollisionError):
            registry.register("wrong-case", "/Blog/", output)
    assert registry.blog_archive() is blog
    with pytest.raises(RouteCollisionError):
        registry.register("output-case", "/other/", "Blog/index.html")
    for path in ("/blog/../", "//blog/", "/blog/?q=1"):
        with pytest.raises(RouteCollisionError):
            registry.route_for_path(path)


def test_sitemap_lists_each_page_once_in_registration_order() -> None:
    registry = RouteRegistry("https://geoqiao.me")
    registry.home()
    registry.blog_archive(1)
    registry.atom()
    registry.robots()
    registry.search()
    registry.blog_detail("post")
    registry.home()  # registering the same route again is harmless
    assert [route.canonical_path for route in registry.sitemap_routes()] == [
        "/",
        "/blog/",
        "/blog/post/",
    ]


def test_unicode_tag_routes_encode_urls_and_keep_raw_file_names() -> None:
    registry = RouteRegistry("https://geoqiao.me")
    tag = registry.tag("示例-标签")
    assert tag.canonical_path == "/tags/%E7%A4%BA%E4%BE%8B-%E6%A0%87%E7%AD%BE/"
    assert tag.canonical_url == f"https://geoqiao.me{tag.canonical_path}"
    assert tag.output_path == "tags/示例-标签/index.html"
    assert registry.route_for_path(tag.canonical_path) is tag
    assert registry.route_for_path("/tags/示例-标签/") is tag
    for key in ("a_b", "a--b", "c++", "x" * 51):
        with pytest.raises(RouteCollisionError):
            registry.tag(key)


def test_extra_pages_are_directory_routes_checked_for_collisions() -> None:
    registry = RouteRegistry("https://geoqiao.me")
    registry.projects()
    page = registry.extra_page("/projects/escaping/")
    assert page.output_path == "projects/escaping/index.html"
    assert registry.route_for_path("/projects/escaping/") is page
    assert registry.extra_page("/projects/escaping/") is page
    for path in ("/Projects/Escaping/", "/now", "now/", "/../x/"):
        with pytest.raises(RouteCollisionError):
            registry.extra_page(path)
