"""Installed-console tracer: replace HTTP transport only, never compiler/adapter."""

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests


def snapshot_response(
    self: requests.Session,
    request: requests.PreparedRequest,
    **kwargs: object,
) -> requests.Response:
    assert isinstance(request.url, str) and request.headers is not None
    url = urlsplit(request.url)
    assert request.method == "GET" and url.hostname == "api.github.com"
    assert url.scheme == "https" and url.port in (None, 443)
    assert request.headers["Authorization"] == "token consumer-fixture"
    path = url.path
    if path == "/repos/alice/site":
        data = {
            "full_name": "alice/site",
            "html_url": "https://github.com/alice/site",
            "url": "https://api.github.com/repos/alice/site",
            "owner": {"login": "alice", "type": "User"},
        }
    elif path == "/repos/alice/site/issues":
        assert parse_qs(url.query)["state"] == ["all"]
        if os.environ.get("CONSUMER_FAIL_ISSUES"):
            raise RuntimeError("consumer-fixture")
        data = [
            {
                "number": number,
                "title": "Plain writing",
                "body": "Visible body.",
                "user": {"login": login},
                "labels": [{"name": "type:blog"}, {"name": "published"}],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
            for number, login in ((128, "alice"), (129, "mallory"))
        ]
    else:
        raise AssertionError(f"Unexpected API request: {path}")
    with Path(os.environ["CONSUMER_REQUEST_LOG"]).open("a", encoding="utf-8") as log:
        log.write(path + "\n")
    response = requests.Response()
    response.status_code = 200
    response.url = request.url
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(data).encode()
    return response


requests.sessions.Session.send = snapshot_response
