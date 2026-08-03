from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()


def test_wheel_consumer_builds_site_outside_checkout(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    dist = tmp_path / "dist"
    subprocess.run(  # noqa: S603
        [uv, "build", "--wheel", "--out-dir", str(dist)],
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(dist.glob("*.whl"))
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    script = """
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, __WHEEL__)
import github_blog
from github_blog.config import Settings
from github_blog.models.issue_snapshot import IssueSnapshot
from github_blog.site_compiler import SiteCompiler
assert '.whl/' in github_blog.__file__.replace('\\\\', '/')

root = Path.cwd()
settings = Settings.model_validate({
    'github': {'repo': 'owner/site', 'allowed_authors': ['owner']},
    'site': {'title': 'Consumer', 'author': 'Owner', 'url': 'https://example.com/'},
    'about': {'issue_number': 2},
    'security': {'token_env': 'TOKEN'},
})
assert settings.theme.name == 'geoqiao.me'
now = datetime(2026, 1, 1, tzinfo=timezone.utc)
snapshots = [
    IssueSnapshot(
        1,
        'Post',
        'owner',
        '---\\nslug: post\\ndescription: A post.\\ncreated_date: "2026-01-01"\\n---\\n\\nBody.',
        ('type:blog', 'published'),
        now,
        now,
        False,
    ),
    IssueSnapshot(
        2,
        'About',
        'owner',
        '---\\ndescription: About.\\ncreated_date: "2026-01-01"\\n---\\n\\nAbout.',
        ('type:about', 'published'),
        now,
        now,
        False,
    ),
]
class FakeGitHub:
    def get_repo(self, name):
        return object()
    def fetch_issue_snapshots(self, repo):
        return snapshots

result = SiteCompiler(
    'unused',
    'owner/site',
    settings,
    config_root=root,
    github_service=FakeGitHub(),
).generate()
assert result.success, result.diagnostics
assert (root / 'output/index.html').is_file()
assert (root / 'output/blog/post/index.html').is_file()
assert (root / 'output/templates/geoqiao.me/static/css/style.css').is_file()
assert (root / 'output/templates/geoqiao.me/static/js/comments.js').is_file()
""".replace("__WHEEL__", repr(str(wheel)))
    subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=consumer,
        check=True,
        capture_output=True,
        text=True,
    )
