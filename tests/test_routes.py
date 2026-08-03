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
    assert registry.url(detail) == "https://geoqiao.me/blog/my-post/"


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


def test_registry_sitemap_membership_excludes_operational_files() -> None:
    registry = RouteRegistry("https://geoqiao.me")
    registry.home()
    registry.blog_archive(1)
    registry.blog_detail("post")
    registry.atom()
    registry.robots()
    paths = registry.sitemap_routes()
    assert "/" in paths and "/blog/post/" in paths
    assert "/atom.xml" not in paths and "/robots.txt" not in paths
