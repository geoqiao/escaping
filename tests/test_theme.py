"""ThemeLoader and LoadedTheme: Theme API 4 manifests, layers, options, strings."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import UndefinedError

import escaping_site.theme as theme_module
from escaping_site.config import ConfigError, PagesConfig
from escaping_site.theme import TEMPLATE_CHAINS, ThemeError, ThemeLoader

_ROOT = Path(__file__).parent.parent.absolute()
#: Every page template a Theme may have.
_ALL_TEMPLATES = tuple(
    dict.fromkeys(name for chain in TEMPLATE_CHAINS.values() for name in chain)
)


def _local_theme(
    root: Path,
    manifest: str = "api: 4\n",
    *,
    templates: tuple[str, ...] = _ALL_TEMPLATES,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "theme.yaml").write_text(manifest, encoding="utf-8")
    for name in templates:
        (root / name).write_text(name, encoding="utf-8")
    return root


def _problems(config_root: Path, use: str) -> list[str]:
    with pytest.raises(ThemeError) as caught:
        ThemeLoader(config_root).load(use)
    assert isinstance(caught.value, ConfigError)
    return caught.value.problems


def test_builtin_quiet_loads_outside_a_checkout_and_publishes_under_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    theme = ThemeLoader(tmp_path).load("quiet")

    assert theme.name == "quiet" and not theme.local_roots
    with pytest.raises(UndefinedError):
        theme.environment().from_string("{{ missing }}").render()
    theme.check()
    theme.copy_static(tmp_path / "output")
    assets = tmp_path / "output" / "assets"
    assert (assets / "css" / "style.css").is_file()
    assert (assets / "js" / "site.js").is_file()
    # Shared scripts are the compiler's, never a Theme's own static files.
    assert not (assets / "escaping").exists()


def test_local_theme_resolves_from_config_root_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    theme_dir = _local_theme(site / "themes" / "mine")
    (theme_dir / "static" / "css").mkdir(parents=True)
    (theme_dir / "static" / "css" / "style.css").write_text("body {}")
    (theme_dir / "static" / ".DS_Store").write_text("finder noise")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    theme = ThemeLoader(site).load("./themes/mine")

    assert theme.local_roots == (theme_dir.resolve(),)
    assert theme.environment().get_template("home.html").render() == "home.html"
    theme.copy_static(site / "output")
    assert (site / "output/assets/css/style.css").read_text() == "body {}"
    assert not (site / "output/assets/.DS_Store").exists()


@pytest.mark.parametrize(
    ("use", "expected"),
    [
        ("quite", "no built-in Theme named quite; did you mean quiet?"),
        ("./missing", "directory ./missing does not exist"),
    ],
)
def test_theme_use_errors_name_the_fix(tmp_path: Path, use: str, expected: str) -> None:
    assert any(expected in problem for problem in _problems(tmp_path, use))


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        ("api: 3\n", "must declare api: 4 (see docs/themes/authoring.md)"),
        ("api: [\n", "is not valid YAML"),
        ("- api\n", "must be a mapping"),
        ("api: 4\nunknown: 1\n", "unknown: unknown field"),
        ("api: 4\nextends: ./parent\n", "extends must name a built-in Theme"),
        (
            "api: 4\noptions:\n  Bad-Name:\n    type: string\n    default: ''\n",
            "options.Bad-Name: use lowercase letters",
        ),
        (
            "api: 4\noptions:\n  size:\n    type: choice\n    default: a\n",
            "options.size: a choice needs values",
        ),
        (
            "api: 4\noptions:\n  wide:\n    type: boolean\n    default: 'yes'\n",
            "options.wide.default: must be true or false",
        ),
        (
            "api: 4\noptions:\n  accent:\n    type: color\n    default: red\n",
            "options.accent.default: must be a hex color",
        ),
        (
            "api: 4\noptions:\n  home:\n    type: url\n    default: 'javascript:alert(1)'\n",
            "options.home.default: link URL must be HTTPS",
        ),
        (
            "api: 4\noptions:\n  picks:\n    type: posts\n    default: [0]\n",
            "must be a list of Blog Issue numbers",
        ),
        ("api: 4\nstrings:\n  en:\n    language: x\n", "strings.en.language"),
    ],
)
def test_manifest_problems_point_at_the_field(
    tmp_path: Path, manifest: str, expected: str
) -> None:
    _local_theme(tmp_path / "theme", manifest)

    problems = _problems(tmp_path, "./theme")

    assert any(expected in problem for problem in problems), problems


def test_symbolic_links_are_rejected(tmp_path: Path) -> None:
    theme_dir = _local_theme(tmp_path / "theme")
    (theme_dir / "static").mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("not for publication")
    (theme_dir / "static" / "leak.txt").symlink_to(secret)
    assert any(
        "static/leak.txt is a symbolic link" in p
        for p in _problems(tmp_path, "./theme")
    )

    (tmp_path / "linked").symlink_to(_local_theme(tmp_path / "real"))
    assert _problems(tmp_path, "./linked") == ["theme.use: ./linked is a symbolic link"]


def test_static_escaping_is_reserved_for_the_compiler(tmp_path: Path) -> None:
    theme_dir = _local_theme(tmp_path / "theme")
    (theme_dir / "static" / "escaping").mkdir(parents=True)
    (theme_dir / "static" / "escaping" / "comments.js").write_text("// mine")

    assert any(
        "static/escaping/ is reserved" in p for p in _problems(tmp_path, "./theme")
    )


def test_extends_cycle_between_builtins_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builtins = tmp_path / "builtins"
    _local_theme(builtins / "a", "api: 4\nextends: b\n")
    _local_theme(builtins / "b", "api: 4\nextends: a\n")
    monkeypatch.setattr(theme_module, "BUILTIN_THEMES", builtins)

    assert any("forms a cycle" in p for p in _problems(tmp_path, "a"))


@pytest.mark.parametrize("parent", ["{outside}", "../outside"])
def test_extends_cannot_reach_a_directory_outside_the_builtins(
    tmp_path: Path, parent: str
) -> None:
    outside = _local_theme(tmp_path / "outside")
    _local_theme(
        tmp_path / "theme", f"api: 4\nextends: {parent.format(outside=outside)}\n"
    )

    assert any("extends must name" in p for p in _problems(tmp_path, "./theme"))


def test_check_reports_every_missing_or_broken_template_before_rendering(
    tmp_path: Path,
) -> None:
    theme_dir = _local_theme(
        tmp_path / "theme",
        templates=tuple(
            n for n in _ALL_TEMPLATES if n not in ("post.html", "tags.html")
        ),
    )
    (theme_dir / "work").mkdir()
    (theme_dir / "work" / "alpha.html").write_text("alpha")
    (theme_dir / "partial.html").write_text("line one\n{% if %}\n")
    theme = ThemeLoader(tmp_path).load("./theme")
    pages = PagesConfig.model_validate(
        {
            "extra": [
                {
                    "path": "/work/{slug}/",
                    "template": "work/{slug}.html",
                    "for_each": "projects",
                }
            ]
        }
    )

    with pytest.raises(ThemeError) as caught:
        theme.check(pages, ["alpha", "beta"])

    problems = caught.value.problems
    assert (
        "theme: missing template post.html (every Theme needs blog.html and "
        "post.html)" in problems
    )
    assert (
        "theme: has no tags.html for the tags page /tags/; add tags.html to the "
        "Theme, or set pages.tags: false in config.yaml" in problems
    )
    assert (
        "pages.extra: /work/beta/ needs template work/beta.html, which theme does "
        "not have" in problems
    )
    assert not any("alpha" in problem for problem in problems)
    assert any(p.startswith("theme: partial.html line 2:") for p in problems)


def test_missing_templates_fall_back_to_blog_and_post() -> None:
    theme = ThemeLoader(_ROOT).load("tests/fixtures/minimal_theme")

    assert {kind: theme.template_for(kind) for kind in TEMPLATE_CHAINS} == {
        "home": "blog.html",
        "blog": "blog.html",
        "ideas": "blog.html",
        "tag": "blog.html",
        "post": "post.html",
        "idea": "post.html",
        "about": "post.html",
        "tags": "tags.html",
        "projects": "projects.html",
    }
    with pytest.raises(ThemeError) as caught:
        theme.check()
    assert [p.split(";")[0] for p in caught.value.problems] == [
        "minimal_theme: has no tags.html for the tags page /tags/",
        "minimal_theme: has no projects.html for the projects page /projects/",
    ]
    theme.check(PagesConfig.model_validate({"tags": False, "projects": False}))


def test_the_url_filter_puts_site_addresses_under_the_sites_path() -> None:
    theme = ThemeLoader(_ROOT).load("tests/fixtures/minimal_theme")
    env = theme.environment("/notes")

    def render(source: str, **values: object) -> str:
        return env.from_string(source).render(**values)

    assert render("{{ '/assets/a.css'|url }}") == "/notes/assets/a.css"
    # Route paths already include it; full URLs and fragments stay as they are.
    for value in ("/notes/blog/", "https://x.test/a", "#top", "//cdn.test/a.js"):
        assert render("{{ value|url }}", value=value) == value
    assert theme.environment().from_string("{{ '/a'|url }}").render() == "/a"
    with pytest.raises(TypeError, match="url expects an address string"):
        render("{{ 3|url }}")


def test_a_child_template_wins_over_the_parent_before_falling_back(
    tmp_path: Path,
) -> None:
    _local_theme(tmp_path / "theme", "api: 4\nextends: quiet\n", templates=())
    theme = ThemeLoader(tmp_path).load("./theme")
    # Quiet has idea.html, so the child's post.html would not stand in for it.
    assert theme.template_for("idea") == "idea.html"


_OPTIONS = """\
api: 4
options:
  label: {type: string, default: Hello}
  wide: {type: boolean, default: false}
  count: {type: integer, default: 3}
  accent: {type: color, default: ""}
  home: {type: url, default: /}
  size: {type: choice, values: [small, large], default: small}
  words: {type: list, default: [a]}
  picks: {type: posts, default: []}
"""


def test_options_apply_defaults_and_check_each_type(tmp_path: Path) -> None:
    _local_theme(tmp_path / "theme", _OPTIONS)
    theme = ThemeLoader(tmp_path).load("./theme")

    defaults = theme.resolve_options({})
    assert vars(defaults) == {
        "label": "Hello",
        "wide": False,
        "count": 3,
        "accent": "",
        "home": "/",
        "size": "small",
        "words": ("a",),
        "picks": (),
    }
    chosen = theme.resolve_options(
        {"accent": "#A72F6A", "size": "large", "picks": [7, 3], "count": 0}
    )
    assert (chosen.accent, chosen.size, chosen.picks, chosen.count) == (
        "#A72F6A",
        "large",
        (7, 3),
        0,
    )

    with pytest.raises(ThemeError) as caught:
        theme.resolve_options(
            {
                "labl": "typo",
                "wide": "yes",
                "count": 1.5,
                "accent": "magenta",
                "home": "http://example.com/",
                "size": "huge",
                "words": "a, b",
                "picks": [3, 3],
            }
        )
    assert caught.value.problems == [
        "theme.options.labl: theme has no such option; did you mean label?",
        "theme.options.wide: must be true or false",
        "theme.options.count: must be a whole number",
        "theme.options.accent: must be a hex color such as #a72f6a",
        "theme.options.home: link URL must be HTTPS, mailto, root-relative, or a "
        "fragment",
        "theme.options.size: must be one of small, large",
        "theme.options.words: must be a list of text",
        "theme.options.picks: lists the same Issue twice",
    ]


@pytest.mark.parametrize(
    ("language", "used", "greeting", "farewell"),
    [
        ("en", "en", "Hello", "Bye"),
        ("fr", "en", "Hello", "Bye"),
        ("zh", "zh", "你好", "Bye"),
        ("zh-CN", "zh", "你好", "Bye"),
        ("zh-TW", "zh-tw", "你好", "再會"),
    ],
)
def test_strings_fall_back_from_full_tag_to_primary_subtag_to_english(
    tmp_path: Path, language: str, used: str, greeting: str, farewell: str
) -> None:
    _local_theme(
        tmp_path / "theme",
        "api: 4\nstrings:\n  en: {hello: Hello, bye: Bye}\n  zh: {hello: 你好}\n"
        "  zh-TW: {bye: 再會}\n",
    )

    t = ThemeLoader(tmp_path).load("./theme").strings_for(language)

    assert (t.language, t.hello, t.bye) == (used, greeting, farewell)


def test_extending_quiet_merges_options_strings_and_static(
    tmp_path: Path,
) -> None:
    theme_dir = _local_theme(
        tmp_path / "theme",
        "api: 4\nextends: quiet\noptions:\n  mood: {type: string, default: calm}\n"
        "strings:\n  en: {footer_thanks: Cheers., extra: More}\n",
        templates=("now.html",),
    )
    (theme_dir / "static" / "css").mkdir(parents=True)
    (theme_dir / "static" / "css" / "style.css").write_text("/* child */")

    theme = ThemeLoader(tmp_path).load("./theme")

    assert [layer.name for layer in theme.layers] == ["./theme", "quiet"]
    theme.check()
    options = theme.resolve_options({"mood": "busy", "tagline": "Hi"})
    assert (options.mood, options.tagline, options.show_powered_by) == (
        "busy",
        "Hi",
        True,
    )
    t = theme.strings_for("en")
    assert (t.footer_thanks, t.extra, t.blog) == ("Cheers.", "More", "Blog")
    files = theme.static_files()
    assert files["css/style.css"] == theme_dir / "static" / "css" / "style.css"
    assert files["js/site.js"].is_relative_to(theme_module.BUILTIN_THEMES / "quiet")
    parent = theme.environment().get_template("@quiet/base.html")
    assert parent.filename == str(theme_module.BUILTIN_THEMES / "quiet" / "base.html")


def test_quiet_docs_list_every_option_and_string_key() -> None:
    quiet = ThemeLoader(_ROOT).load("quiet")
    docs = (_ROOT / "docs/themes/quiet.md").read_text(encoding="utf-8")

    keys = {*quiet.options, *quiet.strings["en"], *quiet.strings["zh"]}
    assert {key for key in keys if f"`{key}`" not in docs} == set()


def test_the_extends_fixture_is_a_complete_theme() -> None:
    theme = ThemeLoader(_ROOT).load("tests/fixtures/extends_theme")

    pages = PagesConfig.model_validate(
        {
            "extra": [
                {"path": "/now/", "template": "now.html"},
                {
                    "path": "/projects/{slug}/",
                    "template": "project.html",
                    "for_each": "projects",
                },
            ]
        }
    )
    theme.check(pages, ["alpha"])
    assert theme.resolve_options({}).now_text == "Working on escaping."
