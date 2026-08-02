from __future__ import annotations

from datetime import datetime, timezone

import pytest

from github_blog.config import Settings
from github_blog.content_compiler import ContentCompiler
from github_blog.models.issue_snapshot import IssueSnapshot
from github_blog.projects import ProjectCompiler
from github_blog.services.render_service import RenderService
from github_blog.site_model import SiteModelBuilder


def _settings(theme: str) -> Settings:
    data: dict[str, object] = {
        "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
        "site": {
            "title": "Site",
            "author": "geoqiao",
            "url": "https://geoqiao.me/",
            "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
        },
        "about": {"issue_number": 10},
        "paths": {"theme": theme},
        "security": {"token_env": "TOKEN"},
    }
    if theme == "geoqiao.me":
        data["theme_lock"] = {
            "repository": "geoqiao/escaping",
            "commit": "e30a52e89645e4e3cd0f1630653c248b9f203c7d",
            "api_version": "1",
        }
    return Settings.model_validate(data)


def _snap(number: int, kind: str, metadata: str) -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=timezone.utc)
    return IssueSnapshot(
        number,
        kind.title(),
        "geoqiao",
        f"---\n{metadata}\n---\n\nBody **content**.",
        (f"type:{kind}", "published"),
        now,
        now,
        False,
    )


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me"])
def test_theme_contract_renders_every_strict_page(theme: str) -> None:
    settings = _settings(theme)
    content = ContentCompiler(settings).compile(
        [
            _snap(
                1, "blog", 'slug: post\ndescription: Post.\ncreated_date: "2026-01-01"'
            ),
            _snap(2, "idea", 'description: Idea.\ncreated_date: "2026-01-02"'),
            _snap(10, "about", 'description: About.\ncreated_date: "2026-01-03"'),
        ]
    )
    site = SiteModelBuilder(settings).build(
        content,
        ProjectCompiler().compile([]),
        build_start_time=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )
    html = RenderService(settings).render_site(site)
    assert not site.has_errors
    assert set(html) >= {
        "index.html",
        "blog/index.html",
        "blog/post/index.html",
        "ideas/index.html",
        "ideas/2/index.html",
        "about/index.html",
        "projects/index.html",
        "tags/index.html",
        "atom.xml",
        "sitemap.xml",
        "robots.txt",
    }
    combined = "\n".join(value for key, value in html.items() if key.endswith(".html"))
    assert "issue-number" in combined and "2" in combined and "10" in combined
    assert "MutationObserver" in combined
    assert "insertAdjacentHTML" in combined
    assert "/templates/" + theme + "/static/" in combined
    assert "created_date:" not in combined and "slug:" not in combined
    assert "<script>alert" not in combined
