from __future__ import annotations

from typing import TypedDict

from .models.site import SiteModel


class SearchItem(TypedDict):
    title: str
    description: str
    tags: list[str]
    type: str
    url: str


class SearchIndex(TypedDict):
    version: int
    items: list[SearchItem]


def build_search_index(site: SiteModel) -> SearchIndex:
    """Project only published models, not Issues, body HTML or archive duplicates."""
    items: list[SearchItem] = [
        {
            "title": post.title,
            "description": post.description,
            "tags": [tag.name for tag in post.tags],
            "type": "Blog",
            "url": post.route.canonical_path,
        }
        for post in site.blogs
    ]
    items.extend(
        SearchItem(
            title=idea.title,
            description=idea.description,
            tags=[tag.name for tag in idea.tags],
            type="Idea",
            url=idea.route.canonical_path,
        )
        for idea in site.ideas
    )
    items.extend(
        SearchItem(
            title=project.title,
            description=project.summary,
            tags=list(project.topics),
            type="Project",
            url=project.page.canonical_path if project.page else project.url,
        )
        for project in site.projects
    )
    return {"version": 1, "items": items}
