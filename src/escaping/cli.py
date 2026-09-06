from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import structlog
from pydantic import ValidationError

from .config import read_config_overrides, read_platform_context, security_from_config
from .services.github_service import GitHubService
from .site_compiler import SiteCompiler
from .site_inputs import resolve_settings

logger = structlog.get_logger()


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Strict GitHub Issue Site Compiler")
    parser.add_argument(
        "--repo",
        help="GitHub repository (owner/name); overrides the configured source repository.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Strict YAML configuration path.",
    )
    parser.add_argument(
        "--context",
        type=Path,
        help="Non-secret GitHub.com repository/Pages root context JSON path.",
    )
    args = parser.parse_args()

    config_path = args.config.expanduser().absolute()
    try:
        overrides = read_config_overrides(config_path)
        context = (
            read_platform_context(args.context) if args.context is not None else None
        )
        security = security_from_config(overrides)
        token = os.environ.get(security.token_env)
        if not token:
            logger.error("missing_token", env_var=security.token_env)
            sys.exit(1)
        github = GitHubService(token)
        settings, input_diagnostics = resolve_settings(
            overrides,
            context=context,
            github_service=github,
            repository_override=args.repo,
        )
    except (OSError, ValueError) as exc:
        message = str(exc)
        if isinstance(exc, ValidationError):
            message = "Invalid input fields: " + ", ".join(
                ".".join(map(str, error["loc"])) for error in exc.errors()
            )
        logger.error("input_failed", message=message)
        sys.exit(1)

    result = SiteCompiler(
        token,
        settings.github.repo,
        settings,
        config_root=config_path.parent,
        github_service=github,
    ).generate()
    for diagnostic in (*input_diagnostics, *result.diagnostics):
        fields: dict[str, str | int] = {
            "code": diagnostic.code,
            "message": diagnostic.message,
        }
        if diagnostic.issue_number is not None:
            fields["issue_number"] = diagnostic.issue_number
        if diagnostic.field is not None:
            fields["field"] = diagnostic.field
        if diagnostic.severity == "error":
            logger.error("build_diagnostic", **fields)
        else:
            logger.warning("build_diagnostic", **fields)
    if not result.success:
        sys.exit(1)
