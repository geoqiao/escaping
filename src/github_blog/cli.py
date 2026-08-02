from __future__ import annotations

import argparse
import sys
from pathlib import Path

import structlog

from .config import GithubConfig, Settings
from .site_compiler import SiteCompiler, token_from_settings

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
    args = parser.parse_args()

    settings = Settings.load_from_yaml(args.config)
    if args.repo:
        settings.github = GithubConfig(
            repo=args.repo,
            allowed_authors=settings.github.allowed_authors,
        )
    token = token_from_settings(settings)
    if not token:
        logger.error("missing_token", env_var=settings.security.token_env)
        sys.exit(1)

    result = SiteCompiler(token, settings.github.repo, settings).generate()
    for diagnostic in result.diagnostics:
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


if __name__ == "__main__":
    run_cli()
