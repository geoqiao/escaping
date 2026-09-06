from datetime import UTC, datetime
from pathlib import Path

from jinja2 import DictLoader

from escaping.config import Settings
from escaping.models.content import ContentCompilationResult
from escaping.projects import ProjectCompiler
from escaping.routes import RouteRegistry
from escaping.services.render_service import RenderService
from escaping.site_builder import SiteBuilder
from escaping.theme import ThemeLoader

_ROOT = Path(__file__).parent.parent.absolute()


def test_featured_projects_are_common_context_for_home_and_about() -> None:
    settings = Settings.model_validate(
        {
            "github": {"repo": "owner/site", "allowed_authors": ["owner"]},
            "site": {
                "title": "Site",
                "author": "Owner",
                "url": "https://example.org/",
            },
            "projects": [
                {"repository": "owner/ignored", "order": 0},
                {
                    "repository": "owner/second",
                    "slug": "second",
                    "featured": True,
                    "order": 2,
                },
                {
                    "repository": "owner/first",
                    "slug": "first",
                    "featured": True,
                    "order": 1,
                },
                {
                    "repository": "owner/last",
                    "slug": "last",
                    "featured": True,
                    "order": 3,
                },
                {
                    "repository": "owner/fourth",
                    "slug": "fourth",
                    "featured": True,
                    "order": 4,
                },
            ],
        }
    )
    routes = RouteRegistry(str(settings.site.url))
    site = SiteBuilder(settings, routes).build(
        ContentCompilationResult(),
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    renderer.env.loader = DictLoader(
        {
            "home.html": "{% for project in featured_projects %}{{ project.slug }}{% if not loop.last %}|{% endif %}{% endfor %}",
            "about.html": "{% for project in featured_projects %}{{ project.slug }}{% if not loop.last %}|{% endif %}{% endfor %}",
            "index.html": "",
            "projects.html": "",
            "tags.html": "",
            "ideas.html": "",
        }
    )
    renderer.env.cache.clear()

    rendered = renderer.render_site(site)

    assert rendered["index.html"] == "first|second|last|fourth"
    assert rendered["about/index.html"] == "first|second|last|fourth"
