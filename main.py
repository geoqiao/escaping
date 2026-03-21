"""
github-blog generator:

`python main.py <github_token> <github_repo>`

Read issues from GitHub and generate HTML articles.

Powered by Jinja2 and PyGithub
"""

import argparse
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from feedgen.feed import FeedGenerator
from github import Auth, Github
from github.Issue import Issue
from github.PaginatedList import PaginatedList
from github.Repository import Repository
from jinja2 import Environment, FileSystemLoader
from lxml.etree import CDATA  # type: ignore
from marko import Markdown
from marko.ext.gfm import GFM

from configs.config_utils import Config
from configs.slug_utils import generate_slug

config = Config()


def main(token: str, repo_name: str):
    dir_init(content_dir=config.content_dir, blog_dir=config.blog_dir)
    user: Github = login(token)
    me: str = get_me(user)
    repo: Repository = get_repo(user, repo_name)
    issues: PaginatedList[Issue] = get_all_issues(repo, me)
    issues_list = list(issues)

    # 为每个 issue 生成 slug 并关联到其 ID，同时提供字符串和整数键以增强模板兼容性
    issue_slugs = {}
    for issue in issues_list:
        issue_tags = [label.name for label in issue.labels] if issue.labels else []
        slug = generate_slug(issue.number, issue_tags)
        issue_slugs[issue.number] = slug
        issue_slugs[str(issue.number)] = slug

    tags = collect_tags(issues_list)
    page_size = config.page_size
    pages = paginate_issues(issues_list, page_size)
    total_pages = max(1, len(pages))

    for page, page_issues in enumerate(pages, start=1):
        pagination = build_pagination(page, total_pages)
        # 将 issue_slugs 转换为 Jinja2 易于读取的格式
        index_blog: str = render_blog_index(page_issues, tags, pagination, issue_slugs)
        save_blog_index_as_html(content=index_blog, page=page)

    for issue in issues_list:
        content: str = render_issue_body(issue, issue_slugs[issue.number])
        save_articles_to_content_dir(
            issue, content=content, slug=issue_slugs[issue.number]
        )

    gen_rss_feed(issues_list, issue_slugs)
    gen_robots_txt()
    gen_sitemap(issues_list, tags, issue_slugs)

    tag_index = build_tag_index(issues_list)
    if tags:
        for tag in tags:
            tag_issues = tag_index.get(tag, [])
            if not tag_issues:
                continue
            tag_content = render_tag_page(tag, tag_issues, tags, issue_slugs)
            save_tag_page(tag, tag_content)
        tags_index_content = render_tags_index(tags, tag_index)
        save_tags_index(tags_index_content)


def dir_init(content_dir: Path, blog_dir: Path):
    """
    A function to initialize directories by removing existing ones and creating new ones.
    """
    if os.path.exists(content_dir):
        shutil.rmtree(content_dir)

    os.mkdir(content_dir)
    os.mkdir(content_dir / blog_dir)


def login(token: str) -> Github:
    """
    Authenticate with GitHub using a token and return a Github instance.

    Uses the new `Auth.Token` API when available (avoids DeprecationWarning),
    and falls back to the older constructor for older PyGithub versions.
    """

    if Auth is not None and hasattr(Auth, "Token"):
        # New PyGithub (>=2.x) style
        return Github(auth=Auth.Token(token))
    # Fallback for older PyGithub
    return Github(token)


def get_me(user: Github) -> str:
    """
    Get the login name of the authenticated user.

    Args:
        user (Github): An authenticated Github instance.

    Returns:
        str: The login name of the authenticated user.
    """
    return user.get_user().login


def get_repo(user: Github, repo_name: str) -> Repository:
    """
    Get a repository by name for a given authenticated user.

    Args:
        user (Github): An authenticated Github instance.
        repo_name (str): The name of the repository to retrieve.

    Returns:
        Repository: A Github repository object.
    """
    return user.get_repo(repo_name)


def is_me(issue: Issue, me: str) -> bool:
    """
    Check if an issue was created by the authenticated user.

    Args:
        issue (Issue): The issue to check.
        me (str): The login name of the authenticated user.

    Returns:
        bool: True if the issue was created by the authenticated user, False otherwise.
    """
    return issue.user.login == me


def get_all_issues(repo: Repository, me: str) -> PaginatedList[Issue]:
    """Get all issues for a given GitHub repository created by a specific user.

    Args:
        repo: The GitHub repository object to retrieve issues from.
        me: The username of the user whose issues to retrieve.

    Returns:
        A PaginatedList of GitHub issue objects created by the specified user.
    """
    issues: PaginatedList[Issue] = repo.get_issues(
        creator=me  # ty:ignore[invalid-argument-type]
    )
    return issues


def paginate_issues(issues: list[Issue], page_size: int) -> list[list[Issue]]:
    if not issues:
        return [[]]
    return [issues[i : i + page_size] for i in range(0, len(issues), page_size)]


def collect_tags(issues: list[Issue]) -> list[str]:
    tags = []
    try:
        tagset = set()
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    tagset.add(label.name)
        tags = sorted(list(tagset))
    except Exception:
        tags = []
    return tags


def build_tag_index(issues: list[Issue]) -> dict[str, list[Issue]]:
    tag_index: dict[str, list[Issue]] = {}
    for issue in issues:
        if not issue.labels:
            continue
        for label in issue.labels:
            name = label.name
            if name not in tag_index:
                tag_index[name] = []
            tag_index[name].append(issue)
    return tag_index


def build_pagination(page: int, total_pages: int) -> dict:
    return {
        "page": page,
        "pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_num": page - 1,
        "next_num": page + 1,
    }


def render_blog_index(
    issues: list[Issue], tags: list[str], pagination: dict, issue_slugs: dict[int, str]
) -> str:
    """
    A function that renders an article list using a provided list of issues.

    Parameters:
    - issues: PaginatedList, a paginated list of issues to render in the article list.
    - issue_slugs: A mapping from issue number to slug.

    Returns:
    - str, the rendered article list HTML content.
    """
    blog_title = config.blog_title
    github_name = config.github_name
    meta_description = config.meta_description
    theme_path = config.theme_path
    google_search_verification = config.google_search_verification
    env = Environment(loader=FileSystemLoader(theme_path))
    template = env.get_template("index.html")

    return template.render(
        issues=issues,
        issue_slugs=issue_slugs,
        tags=tags,
        pagination=pagination,
        blog_title=blog_title,
        github_name=github_name,
        github_repo=config.github_repo,
        blog_url=config.blog_url,
        rss_atom_path=config.rss_atom_path,
        author_name=config.author_name,
        meta_description=meta_description,
        google_search_verification=google_search_verification,
    )


def save_blog_index_as_html(content: str, page: int):
    """
    Save the provided content as an HTML file at the specified path.

    Parameters:
    content (str): The content to be written to the HTML file.
    """
    if page == 1:
        path = config.content_dir / "index.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    page_dir = config.content_dir / "page"
    page_dir.mkdir(parents=True, exist_ok=True)
    page_path = page_dir / f"{page}.html"
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(content)


def render_tag_page(
    tag: str, issues: list[Issue], tags: list[str], issue_slugs: dict[int, str]
) -> str:
    blog_title = config.blog_title
    github_name = config.github_name
    meta_description = config.meta_description
    theme_path = config.theme_path
    env = Environment(loader=FileSystemLoader(theme_path))
    template = env.get_template("tag.html")
    return template.render(
        tag_name=tag,
        issues=issues,
        issue_slugs=issue_slugs,
        tags=tags,
        blog_title=blog_title,
        github_name=github_name,
        github_repo=config.github_repo,
        blog_url=config.blog_url,
        rss_atom_path=config.rss_atom_path,
        author_name=config.author_name,
        meta_description=meta_description,
    )


def save_tag_page(tag: str, content: str):
    tag_dir = config.content_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    path = tag_dir / f"{tag}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def render_tags_index(tags: list[str], tag_index: dict[str, list[Issue]]) -> str:
    blog_title = config.blog_title
    github_name = config.github_name
    meta_description = config.meta_description
    theme_path = config.theme_path
    env = Environment(loader=FileSystemLoader(theme_path))
    template = env.get_template("tags.html")
    tag_items = [{"name": tag, "count": len(tag_index.get(tag, []))} for tag in tags]
    return template.render(
        tag_items=tag_items,
        tags=tags,
        blog_title=blog_title,
        github_name=github_name,
        github_repo=config.github_repo,
        blog_url=config.blog_url,
        rss_atom_path=config.rss_atom_path,
        author_name=config.author_name,
        meta_description=meta_description,
    )


def save_tags_index(content: str):
    tags_dir = config.content_dir / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    path = tags_dir / "index.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def markdown2html(mdstr: str) -> str:
    markdown = Markdown(extensions=[GFM, "pangu"])
    html = markdown.convert(mdstr)
    return html


def render_issue_body(issue: Issue, slug: str) -> str:
    """
    Render the body of an issue by converting markdown to HTML and injecting it into a template.

    Parameters:
    issue (Issue): The issue object containing the body to render.
    slug (str): The slug for the issue.

    Returns:
    str: The rendered HTML body of the issue.
    """
    html_body = markdown2html(issue.body)
    blog_title = config.blog_title
    github_name = config.github_name
    meta_description = config.meta_description
    theme_path = config.theme_path
    env = Environment(loader=FileSystemLoader(theme_path))
    template = env.get_template("post.html")
    return template.render(
        issue=issue,
        slug=slug,
        html_body=html_body,
        blog_title=blog_title,
        github_name=github_name,
        github_repo=config.github_repo,
        author_name=config.author_name,
        author_email=config.author_email,
        blog_url=config.blog_url,
        rss_atom_path=config.rss_atom_path,
        meta_description=meta_description,
    )


def save_articles_to_content_dir(issue: Issue, content: str, slug: str):
    # 使用 slug 作为文件名
    path = config.content_dir / config.blog_dir / f"{slug}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def gen_rss_feed(issues: list[Issue], issue_slugs: dict[int, str]):
    """Generate an RSS feed for the given issues.

    Args:
        issues (list): A list of GitHub issue objects.
        issue_slugs (dict): A mapping from issue number to slug.

    Returns:
        None
    """
    fg = FeedGenerator()
    fg.id(config.blog_url)
    fg.title(config.blog_title)
    fg.author({"name": config.author_name, "email": config.author_email})
    fg.link(href=config.blog_url, rel="alternate")
    fg.description(f"""{config.meta_description}""")

    for issue in issues:
        slug = issue_slugs[issue.number]
        fe = fg.add_entry()
        # 修复 RSS 链接：确保包含 contents/ 且处理斜杠
        blog_dir_str = str(config.blog_dir).strip("/")
        url = f"{config.blog_url.rstrip('/')}/contents/{blog_dir_str}/{slug}.html"
        fe.id(url)
        # 使用新的标题格式：ID + Tags
        issue_tags = (
            " ".join([label.name for label in issue.labels]) if issue.labels else ""
        )
        fe.title(f"{issue.number} {issue_tags}".strip())
        fe.link(href=url)
        fe.description(issue.body[:100])
        fe.published(issue.created_at)
        fe.updated(issue.updated_at)
        fe.content(CDATA(markdown2html(issue.body)), type="html")

    fg.atom_file(config.content_dir / config.rss_atom_path)


def gen_robots_txt():
    """Generate robots.txt file using a template."""
    env = Environment(loader=FileSystemLoader("templates/seo"))
    template = env.get_template("robots.txt.j2")
    content = template.render(base_url=config.blog_url.rstrip("/"))
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(content)


def gen_sitemap(issues: list[Issue], tags: list[str], issue_slugs: dict[int, str]):
    """Generate sitemap.xml file using a template."""
    base_url = config.blog_url
    now = datetime.now().strftime("%Y-%m-%d")

    # 准备文章数据
    blog_items = []
    for issue in issues:
        blog_items.append(
            {
                "slug": issue_slugs[issue.number],
                "lastmod": issue.updated_at.strftime("%Y-%m-%d"),
            }
        )

    env = Environment(loader=FileSystemLoader("templates/seo"))
    template = env.get_template("sitemap.xml.j2")
    content = template.render(
        base_url=base_url.rstrip("/"),
        now=now,
        blog_items=blog_items,
        blog_dir=str(config.blog_dir).strip("/"),
        tags=tags,
    )

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(content)


@contextmanager
def timer_context():
    """
    A context manager that measures the execution time of the code within its scope.

    This context manager starts a timer when entering the context and stops the timer when exiting the context. It then prints the elapsed time in seconds.

    Usage:
    with timer_context():
        # Code to measure execution time
    """
    start_time = time.perf_counter()
    yield
    end_time = time.perf_counter()
    print(f"The script has finished running, and it took {end_time - start_time} s。")


if __name__ == "__main__":
    with timer_context():
        parser = argparse.ArgumentParser()
        parser.add_argument("github_token", help="<github_token>")
        parser.add_argument("github_repo", help="<github_repo>")
        options = parser.parse_args()

        main(options.github_token, options.github_repo)
