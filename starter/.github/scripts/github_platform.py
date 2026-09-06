"""Read GitHub.com version/Pages identity; never set up or modify the platform."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

UPSTREAM = "geoqiao/escaping"  # Maintainer-owned source, never Issue/actor input.
API = "https://api.github.com/"
SHA = re.compile(r"[0-9a-f]{40}")
REPO = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+")


class DeliveryError(ValueError):
    """Safe diagnostic: do not expose response bodies or credentials."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None  # Never forward Authorization to an API-provided redirect.


def get(path: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.environ.get("PLATFORM_TOKEN"):
        headers["Authorization"] = "Bearer " + token
    request = Request(API + path, headers=headers)  # noqa: S310 - fixed HTTPS host
    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except HTTPError as exc:
        raise DeliveryError(
            f"GitHub GET failed ({exc.code}); stop, no main fallback"
        ) from None
    except Exception:
        raise DeliveryError("GitHub request/JSON failed; stop") from None


def full_sha(value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise DeliveryError("expected full lowercase commit SHA")
    return value


def release_tag(value: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}", value)
        or ".." in value
        or "//" in value
        or value.endswith("/")
    ):
        raise DeliveryError("expected stable, a formal release tag, or a full SHA")
    return value


def select_version(selection: str = "stable") -> dict:
    prefix = "repos/" + UPSTREAM
    if SHA.fullmatch(selection):
        commit = get(prefix + "/commits/" + selection)
        if (
            full_sha(commit["sha"]) != selection
            or commit.get("url") != API + prefix + "/commits/" + selection
        ):
            raise DeliveryError("fixed commit identity mismatch")
        return {
            "source": UPSTREAM,
            "channel": "fixed",
            "commit": selection,
            "release_id": None,
            "tag": None,
        }
    release_tag(selection)
    endpoint = (
        "/releases/latest"
        if selection == "stable"
        else "/releases/tags/" + quote(selection, safe="")
    )
    release = get(prefix + endpoint)  # Resolve latest once, never during install/build.
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise DeliveryError("release is not formally published stable content")
    try:
        published = datetime.fromisoformat(
            release["published_at"].replace("Z", "+00:00")
        )
        if published.utcoffset() is None:
            raise ValueError
    except KeyError, TypeError, AttributeError, ValueError:
        raise DeliveryError("release has no valid publication time") from None
    if type(release.get("id")) is not int or release["id"] <= 0:
        raise DeliveryError("invalid release identity")
    if release.get("url") != f"{API}{prefix}/releases/{release['id']}":
        raise DeliveryError("release source mismatch")
    tag = release_tag(release["tag_name"])
    if selection != "stable" and (
        selection != tag or release.get("immutable") is not True
    ):
        raise DeliveryError("fixed tag requires a matching immutable formal release")
    ref = get(prefix + "/git/ref/tags/" + quote(tag, safe=""))
    if (
        ref.get("ref") != "refs/tags/" + tag
        or unquote(ref.get("url", "")) != API + prefix + "/git/refs/tags/" + tag
    ):
        raise DeliveryError("tag reference identity mismatch")
    obj = ref["object"]
    seen: set[str] = set()
    for _ in range(8):
        sha = full_sha(obj["sha"])
        kind = obj["type"]
        if kind not in {"commit", "tag"} or sha in seen:
            raise DeliveryError("invalid/cyclic tag target")
        path = f"{prefix}/git/{kind}s/{sha}"
        if obj.get("url") != API + path:
            raise DeliveryError("Git object source mismatch")
        target = get(path)  # Construct the URL; never follow obj['url'].
        if full_sha(target["sha"]) != sha or target.get("url") != API + path:
            raise DeliveryError("Git object identity mismatch")
        if kind == "commit":
            return {
                "source": UPSTREAM,
                "channel": "stable" if selection == "stable" else "fixed",
                "commit": sha,
                "release_id": release["id"],
                "tag": tag,
                "published_at": release["published_at"],
                "immutable": release.get("immutable") is True,
            }
        seen.add(sha)
        obj = target["object"]
    raise DeliveryError("tag chain too deep")


def trusted_context(repository: str, repo: dict, pages: dict) -> dict:
    if (
        not REPO.fullmatch(repository)
        or repo.get("full_name", "").casefold() != repository.casefold()
    ):
        raise DeliveryError("repository identity mismatch")
    owner = repo["owner"]
    if owner.get("login", "").casefold() != repository.split("/")[
        0
    ].casefold() or owner.get("type") not in {"User", "Organization"}:
        raise DeliveryError("repository owner identity/type mismatch")
    url = pages.get("html_url")
    if (
        not isinstance(url, str)
        or any(c.isspace() or ord(c) < 32 or 0x7F <= ord(c) <= 0x9F for c in url)
        or any(c in url for c in "\\?#")
    ):
        raise DeliveryError("invalid Pages URL")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DeliveryError("Pages URL must be a clean HTTPS origin")
    _ = parsed.port  # Validate malformed/out-of-range ports before emitting context.
    if parsed.path not in {"", "/"}:
        raise DeliveryError(
            "project Pages subpaths are unsupported; never truncate them"
        )
    if pages.get("build_type") != "workflow":
        raise DeliveryError("enable Pages with Source: GitHub Actions before building")
    return {
        "repository": repo["full_name"],
        "owner_login": owner["login"],
        "owner_type": owner["type"],
        "pages_base_url": url.rstrip("/") + "/",
        "pages_base_path": "/",
    }


if __name__ == "__main__":
    try:
        if sys.argv[1] == "version":
            result = select_version(os.environ.get("ESCAPING_VERSION", "stable"))
        elif sys.argv[1] == "context":
            repository = os.environ["GITHUB_REPOSITORY"]
            if not REPO.fullmatch(repository) or repository.split("/")[1] in {
                ".",
                "..",
            }:
                raise DeliveryError("invalid repository")
            result = trusted_context(
                repository,
                get("repos/" + repository),
                get("repos/" + repository + "/pages"),
            )
        else:
            raise DeliveryError("unknown command")
        print(json.dumps(result, separators=(",", ":")))
    except Exception as exc:
        detail = (
            str(exc)
            if isinstance(exc, DeliveryError)
            else "invalid platform response/input"
        )
        print(f"Delivery boundary stopped: {detail}", file=sys.stderr)
        sys.exit(1)
