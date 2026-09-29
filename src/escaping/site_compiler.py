"""Build pipeline: check local inputs -> fetch Issues -> compile -> render ->
validate -> publish. No Issue is read until the Config, the Theme and the
output directory have passed their checks; a Theme on GitHub is downloaded
without the token. Config defaults read from GitHub (see ``site_inputs``) are
filled in before this pipeline starts.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from jinja2 import TemplateError, TemplateSyntaxError

from .artifact_validation import SiteArtifactValidator, audit_seo
from .build_result import BuildResult, Diagnostic
from .config import AboutConfig, ConfigError, Settings
from .content_compiler import ContentCompiler
from .models.issue_snapshot import IssueSnapshot
from .models.site import SiteModel
from .output_safety import OutputContainmentError
from .output_staging import OutputStagingError, OutputStagingService
from .projects import ProjectCompiler, ProjectEnrichment
from .remote_theme import download
from .routes import RouteRegistry
from .services.render_service import RenderedSite, RenderService
from .site_builder import SiteBuilder, register_fixed_routes
from .theme import Fetch, LoadedTheme, ThemeLoader

logger = logging.getLogger(__name__)

IssueSource = Callable[[], Sequence[IssueSnapshot]]
ProjectEnricher = Callable[[str], ProjectEnrichment]

#: Warnings about the Issues a Config names; sample Issues cannot match them.
_NEEDS_REAL_ISSUES = frozenset({"THEME_OPTION_POST_MISSING", "REDIRECT_LEFT_OUT"})


@contextmanager
def theme_downloads() -> Iterator[Fetch]:
    """Download GitHub Themes into a directory that lasts until the build ends."""
    with tempfile.TemporaryDirectory(prefix="escaping-themes-") as directory:
        yield partial(download, into=Path(directory))


def prepare_theme(
    settings: Settings, config_root: Path, fetch: Fetch | None = None
) -> tuple[LoadedTheme, SimpleNamespace]:
    """Load the Theme, resolve its options and compile every template.

    Raises:
        ThemeError: With every problem found, before any Issue is read.
    """
    theme = ThemeLoader(config_root, fetch).load(settings.theme.use)
    options = theme.resolve_options(settings.theme.options)
    theme.check(settings.pages, (project.slug for project in settings.projects))
    return theme, options


def compile_site(
    settings: Settings,
    snapshots: Sequence[IssueSnapshot],
    theme: LoadedTheme,
    *,
    project_enricher: ProjectEnricher | None,
    build_start_time: datetime,
) -> SiteModel:
    routes = RouteRegistry(str(settings.site.url), settings.pages.sections())
    register_fixed_routes(routes)  # the sitemap lists them first
    content = ContentCompiler(settings, route_registry=routes).compile(snapshots)
    projects = ProjectCompiler(project_enricher, base=routes.base).compile(
        settings.projects
    )
    return SiteBuilder(settings, route_registry=routes).build(
        content, projects, pages=settings.pages.extra, build_start_time=build_start_time
    )


def render_site(
    directory: Path, site: SiteModel, theme: LoadedTheme, options: SimpleNamespace
) -> RenderedSite:
    renderer = RenderService(theme, options)
    renderer.copy_assets(directory)
    rendered = renderer.render_site(site)
    for relative_path, content in rendered.files.items():
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe output path: {relative_path}")
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return rendered


class SiteCompiler:
    """Build and publish one site; see the module docstring for the order."""

    def __init__(
        self,
        settings: Settings,
        *,
        config_root: Path,
        issues: IssueSource,
        project_enricher: ProjectEnricher | None = None,
    ) -> None:
        if not config_root.is_absolute():
            raise ValueError("SiteCompiler config_root must be absolute")
        self.settings = settings
        self.config_root = config_root
        self.issues = issues
        self.project_enricher = project_enricher

    def generate(self) -> BuildResult:
        with theme_downloads() as fetch:
            return self._generate(fetch)

    def _generate(self, fetch: Fetch) -> BuildResult:
        build_start = datetime.now(UTC)
        try:
            theme, options = prepare_theme(self.settings, self.config_root, fetch)
            staging = OutputStagingService(self.settings.paths.output, self.config_root)
            _check_theme_outside_output(theme, staging.output)
            staging.check_replaceable()
        except ConfigError as exc:
            return _failed("THEME_INVALID", *exc.problems)
        except (OutputContainmentError, OutputStagingError) as exc:
            return _failed("OUTPUT_UNSAFE", str(exc))

        try:
            snapshots = self.issues()
        except Exception as exc:
            # Never show the exception text: client errors may echo request data.
            return _failed(
                "FETCH_FAILED",
                "could not read the Issues of the content repository "
                f"({type(exc).__name__}); check the token and repository",
            )

        site = compile_site(
            self.settings,
            snapshots,
            theme,
            project_enricher=self.project_enricher,
            build_start_time=build_start,
        )
        diagnostics = list(site.diagnostics)
        if site.has_errors:
            return BuildResult(False, tuple(diagnostics))

        staging_dir: Path | None = None
        try:
            staging_dir = staging.create_staging_directory()
            rendered = render_site(staging_dir, site, theme, options)
            diagnostics.extend(rendered.diagnostics)
            problems = SiteArtifactValidator(site).validate(staging_dir)
            diagnostics.extend(problems)
            if any(d.severity == "error" for d in problems):
                return _cleanup(staging, staging_dir, diagnostics)
            diagnostics.extend(staging.publish(staging_dir))
            return BuildResult(True, tuple(diagnostics), site.skipped_issues)
        except TemplateError as exc:
            diagnostics.append(
                Diagnostic(
                    "error", "TEMPLATE_RENDER_FAILED", _template_error(exc, theme)
                )
            )
            return _cleanup(staging, staging_dir, diagnostics)
        except OutputStagingError as exc:
            diagnostics.append(Diagnostic("error", "PUBLISH_FAILED", str(exc)))
            if exc.recovery_paths:
                return BuildResult(False, tuple(diagnostics))
            return _cleanup(staging, staging_dir, diagnostics)
        except Exception as exc:
            logger.exception("The build stopped on an unexpected error:")
            diagnostics.append(Diagnostic("error", "BUILD_FAILED", str(exc)))
            return _cleanup(staging, staging_dir, diagnostics)


def check_theme(
    settings: Settings,
    *,
    config_root: Path,
    snapshots: Sequence[IssueSnapshot] | None = None,
) -> BuildResult:
    """Render the site into a temporary directory and report problems.

    Without ``snapshots`` a few sample Issues stand in for real content, so
    only a Theme on GitHub needs the network. SEO findings are warnings.
    """
    with theme_downloads() as fetch:
        return _check_theme(settings, config_root, snapshots, fetch)


def _check_theme(
    settings: Settings,
    config_root: Path,
    snapshots: Sequence[IssueSnapshot] | None,
    fetch: Fetch,
) -> BuildResult:
    try:
        theme, options = prepare_theme(settings, config_root, fetch)
    except ConfigError as exc:
        return _failed("THEME_INVALID", *exc.problems)
    sample = snapshots is None
    if snapshots is None:
        settings, snapshots = _sample_content(settings)
    site = compile_site(
        settings,
        snapshots,
        theme,
        project_enricher=None,
        build_start_time=datetime.now(UTC),
    )
    diagnostics = list(site.diagnostics)
    if not site.has_errors:
        with tempfile.TemporaryDirectory(prefix="escaping-theme-check-") as tmp:
            directory = Path(tmp)
            try:
                rendered = render_site(directory, site, theme, options)
            except TemplateError as exc:
                diagnostics.append(
                    Diagnostic(
                        "error", "TEMPLATE_RENDER_FAILED", _template_error(exc, theme)
                    )
                )
            else:
                diagnostics.extend(rendered.diagnostics)
                diagnostics.extend(SiteArtifactValidator(site).validate(directory))
                diagnostics.extend(audit_seo(site, directory))
    if sample:
        diagnostics = [d for d in diagnostics if d.code not in _NEEDS_REAL_ISSUES]
    success = not any(d.severity == "error" for d in diagnostics) and not (
        site.has_errors
    )
    return BuildResult(success, tuple(diagnostics), site.skipped_issues)


def _sample_content(settings: Settings) -> tuple[Settings, list[IssueSnapshot]]:
    author = settings.github.allowed_authors[0]
    created = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)

    def issue(
        number: int, title: str, labels: tuple[str, ...], body: str
    ) -> IssueSnapshot:
        return IssueSnapshot(
            number, title, author, body, ("published", *labels), created, created, False
        )

    pages = settings.pages
    issues = [
        issue(
            1,
            "A sample post",
            ("type:blog", "tag:Sample", "tag:示例 标签"),
            '---\ndescription: "A sample post with code, a table and a diagram."\n'
            f"---\n## A heading\n\nText with a [link to the Blog]({pages.blog}) "
            "and `inline code`.\n\n```python\nprint('hello')\n```\n\n"
            "| A | B |\n| - | - |\n| 1 | 2 |\n\n```mermaid\ngraph LR\n  A --> B\n```\n",
        ),
    ]
    # One more post than fits on a Blog page, so page 2 is rendered too.
    issues.extend(
        issue(number, f"Sample post {number}", ("type:blog", "tag:Sample"), "Short.")
        for number in range(100, 100 + settings.paths.page_size)
    )
    if pages.ideas:
        issues.append(
            issue(3, "A sample idea", ("type:idea", "tag:Thought"), "A short thought.")
        )
    if not pages.about:
        return settings, issues
    about = 4
    issues.append(issue(about, "About", ("type:about",), "A sample About page."))
    return settings.model_copy(
        update={"about": AboutConfig(issue_number=about)}
    ), issues


def _check_theme_outside_output(theme: LoadedTheme, output: Path) -> None:
    for root in theme.local_roots:
        if root.is_relative_to(output) or output.is_relative_to(root):
            raise OutputStagingError(
                f"the Theme directory {root} and paths.output {output} overlap; "
                "a build replaces the output and would delete the Theme"
            )


def _template_error(exc: TemplateError, theme: LoadedTheme) -> str:
    """The error with the Theme file and line where rendering stopped."""
    if isinstance(exc, TemplateSyntaxError):
        return f"{exc.name or '<unknown>'} line {exc.lineno}: {exc.message}"
    # Jinja rewrites the traceback so template frames carry the template's
    # file name and line; the innermost one is where the error happened.
    location = None
    tb = exc.__traceback__
    while tb is not None:
        if "__jinja_exception__" in tb.tb_frame.f_globals:
            location = (Path(tb.tb_frame.f_code.co_filename), tb.tb_lineno)
        tb = tb.tb_next
    if location is None:
        return str(exc)
    path, line = location
    for layer in theme.layers:
        if path.is_relative_to(layer.root):
            return f"{layer.name}/{path.relative_to(layer.root)} line {line}: {exc}"
    return f"{path.name} line {line}: {exc}"


def _failed(code: str, *messages: str) -> BuildResult:
    return BuildResult(
        False, tuple(Diagnostic("error", code, message) for message in messages)
    )


def _cleanup(
    staging: OutputStagingService,
    staging_dir: Path | None,
    diagnostics: list[Diagnostic],
) -> BuildResult:
    if staging_dir is not None:
        try:
            diagnostics.extend(staging.cleanup(staging_dir))
        except Exception as exc:
            diagnostics.append(Diagnostic("error", "CLEANUP_FAILED", str(exc)))
    return BuildResult(False, tuple(diagnostics))
