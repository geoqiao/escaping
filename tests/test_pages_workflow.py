from __future__ import annotations

from pathlib import Path

import yaml

_WORKFLOW = Path(__file__).parent.parent / "docs" / "deployment" / "geoqiao-pages.yml"


def _text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_pages_workflow_is_valid_yaml_with_issue_triggers() -> None:
    text = _text()
    assert isinstance(yaml.safe_load(text), dict)
    assert "workflow_dispatch:" in text
    assert "types: [opened, edited, labeled, unlabeled, closed, reopened]" in text
    assert 'paths:\n      - ".github/workflows/pages.yml"' in text
    assert "issue_comment" not in text


def test_pages_workflow_uses_least_privilege_and_pages_actions() -> None:
    text = _text()
    assert "contents: read" in text
    assert "issues: read" in text
    assert "pages: write" in text
    assert "id-token: write" in text
    assert "actions/upload-pages-artifact@v3" in text
    assert "actions/deploy-pages@v4" in text
    assert "GITHUB_TOKEN: ${{ github.token }}" in text
    assert "G_T" not in text


def test_pages_workflow_checks_out_compiler_without_push_deployment() -> None:
    text = _text()
    assert "repository: geoqiao/escaping" in text
    assert "ref: main" in text
    assert "path: compiler" in text
    assert "working-directory: compiler" in text
    assert "x-access-token" not in text
    assert "git push" not in text
