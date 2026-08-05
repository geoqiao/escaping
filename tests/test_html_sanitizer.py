"""Allowlist-based HTML sanitizer tests.

Preserves safe Markdown-rendered HTML while removing dangerous elements,
event-handler attributes, and dangerous URL schemes.  Uses only stdlib.

Key security regressions: entity-decoded injection, attribute-quote breakout,
obfuscated URL schemes (assert href/src removed), and void dangerous tags
that must not suppress following siblings (GFM task-list).
"""

from __future__ import annotations

import pytest

from escaping.utils.html_sanitizer import sanitize_html


@pytest.mark.parametrize(
    "html, expected",
    [
        ("<p>Hello world.</p>", ["<p>Hello world.</p>"]),
        ("<h1>T</h1><h2>S</h2>", ["<h1>T</h1>", "<h2>S</h2>"]),
        ("<ul><li>one</li><li>two</li></ul>", ["<ul><li>one</li><li>two</li></ul>"]),
        (
            "<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>",
            ["<table>", "<th>A</th>", "<td>1</td>"],
        ),
        (
            '<img src="https://example.com/img.png" alt="alt" />',
            ['src="https://example.com/img.png"', 'alt="alt"'],
        ),
        ('<a href="https://example.com">link</a>', ['href="https://example.com"']),
        ("<blockquote><p>Quote.</p></blockquote>", ["<blockquote>"]),
        (
            "<p><strong>bold</strong> and <em>italic</em></p>",
            ["<strong>bold</strong>", "<em>italic</em>"],
        ),
        (
            '<pre><code class="language-python">print(1)\n</code></pre>',
            ["<pre>", "print(1)"],
        ),
    ],
    ids=[
        "p",
        "headings",
        "ul",
        "table",
        "img",
        "link",
        "blockquote",
        "emphasis",
        "pre-code",
    ],
)
def test_safe_content_preserved(html: str, expected: list[str]) -> None:
    result = sanitize_html(html)
    for s in expected:
        assert s in result


def test_misc_safe_content() -> None:
    assert "<hr" in sanitize_html("<hr/>")
    assert "<br" in sanitize_html("<br/>")
    assert sanitize_html("just text") == "just text"
    assert sanitize_html("") == ""


def test_images_receive_browser_loading_defaults() -> None:
    result = sanitize_html(
        '<img src="https://example.com/photo.png" alt="A useful description" '
        'width="1200" height="800">'
    )

    assert 'loading="lazy"' in result
    assert 'decoding="async"' in result


def test_bare_relative_href_is_removed() -> None:
    result = sanitize_html('<a href="not-a-site-route">text</a>')
    assert 'href="not-a-site-route"' not in result
    assert ">text</a>" in result


@pytest.mark.parametrize(
    "html, must_absent",
    [
        ("<p>safe</p><script>alert('xss')</script>", ["<script", "alert"]),
        ("<p>safe</p><style>body{color:red}</style>", ["<style", "color:red"]),
        ('<p>safe</p><iframe src="https://evil.com"></iframe>', ["<iframe"]),
        (
            "<p>safe</p><form action='evil.com'><input name='x'></form>",
            ["<form", "<input"],
        ),
        ("<script>document.cookie</script><p>safe</p>", ["document.cookie"]),
    ],
    ids=["script", "style", "iframe", "form", "script-content"],
)
def test_dangerous_elements_removed(html: str, must_absent: list[str]) -> None:
    result = sanitize_html(html)
    for s in must_absent:
        assert s not in result.lower()
    assert "safe" in result


def test_dangerous_container_suppresses_content() -> None:
    assert "alert" not in sanitize_html("<script>alert(1)</script><p>Safe.</p>")
    assert (
        sanitize_html("<script>alert(1)</script><p>Safe.</p>").count("<p>Safe.</p>")
        == 1
    )


@pytest.mark.parametrize(
    "html, preserved",
    [
        ('<p onclick="alert(1)">text</p>', "<p>text</p>"),
        ('<img src="x" onerror="alert(1)" alt="a" />', 'alt="a"'),
        (
            '<a href="https://example.com" onmouseover="alert(1)">link</a>',
            'href="https://example.com"',
        ),
    ],
    ids=["onclick", "onerror", "onmouseover"],
)
def test_event_handler_attrs_removed(html: str, preserved: str) -> None:
    result = sanitize_html(html)
    assert "onclick" not in result.lower()
    assert "onerror" not in result.lower()
    assert "onmouseover" not in result.lower()
    assert preserved in result


@pytest.mark.parametrize(
    "html",
    [
        '<a href="javascript:alert(1)">click</a>',
        '<img src="javascript:alert(1)" alt="x" />',
        '<a href="data:text/html,<script>alert(1)</script>">x</a>',
        '<a href="vbscript:msgbox(1)">x</a>',
    ],
    ids=["js-href", "js-src", "data-href", "vbscript"],
)
def test_dangerous_url_schemes_removed(html: str) -> None:
    result = sanitize_html(html)
    assert "javascript:" not in result.lower()
    assert "data:" not in result.lower()
    assert "vbscript:" not in result.lower()


@pytest.mark.parametrize(
    "href, expected",
    [
        ("https://example.com", 'href="https://example.com"'),
        ("/page/", 'href="/page/"'),
        ("#section", 'href="#section"'),
        ("mailto:user@example.com", 'href="mailto:user@example.com"'),
    ],
    ids=["https", "relative", "anchor", "mailto"],
)
def test_safe_urls_preserved(href: str, expected: str) -> None:
    assert expected in sanitize_html(f'<a href="{href}">link</a>')


@pytest.mark.parametrize(
    "html, must_absent, must_present",
    [
        (
            "&lt;script&gt;alert(1)&lt;/script&gt;<p>Safe.</p>",
            "<script",
            "&lt;script&gt;",
        ),
        (
            "&lt;img src=x onerror=alert(1)&gt;<p>Safe.</p>",
            "<img",
            "alert(1)",
        ),
        (
            "&lt;iframe src='javascript:alert(1)'&gt;&lt;/iframe&gt;<p>Safe.</p>",
            "<iframe",
            "alert(1)",
        ),
    ],
    ids=["script", "img", "iframe"],
)
def test_entity_decoded_injection_neutralized(
    html: str, must_absent: str, must_present: str
) -> None:
    result = sanitize_html(html)
    assert must_absent not in result.lower()
    # Escaped visible text is preserved (re-escaped, not live tags)
    assert must_present in result
    # Safe sibling content survives
    assert "<p>Safe.</p>" in result


@pytest.mark.parametrize(
    "html, must_present",
    [
        (
            '<img src="x" alt="a&quot; onmouseover=&quot;alert(1)" />',
            'src="x"',
        ),
        (
            '<a href="https://example.com&quot; onclick=&quot;alert(1)">link</a>',
            ">link</a>",
        ),
        (
            '<a href="https://example.com" title="test&quot; onmouseover=&quot;alert(1)">link</a>',
            'href="https://example.com"',
        ),
        ("<img src='x' alt='a' onmouseover='alert(1)' />", 'src="x"'),
        (
            '<a href="https://example.com/?q=&quot;safe&quot;" title="A &quot;quoted&quot; title">link</a>',
            'href="https://example.com/?q=&quot;safe&quot;" title="A &quot;quoted&quot; title"',
        ),
    ],
    ids=["alt", "href", "title", "single-quote", "benign-quoted-attributes"],
)
def test_attribute_quote_escaping(html: str, must_present: str) -> None:
    result = sanitize_html(html)
    assert 'onmouseover="' not in result.lower()
    assert "onmouseover='" not in result.lower()
    assert 'onclick="' not in result.lower()
    assert "onclick='" not in result.lower()
    # Legitimate link/text survives and href values are correctly escaped
    assert must_present in result


# Obfuscated javascript: MUST cause href/src to be removed entirely.
_OBFUSCATED = [
    ('<a href="java\tscript:alert(1)">click</a>', "href="),
    ('<a href="java\nscript:alert(1)">click</a>', "href="),
    ('<a href="java\rscript:alert(1)">click</a>', "href="),
    ('<a href="java\u2028script:alert(1)">click</a>', "href="),
    ('<a href="java\u2029script:alert(1)">click</a>', "href="),
    ('<a href="java\u200bscript:alert(1)">click</a>', "href="),
    ('<img src="java\tscript:alert(1)" alt="x" />', "src="),
]


@pytest.mark.parametrize(
    "html, attr", _OBFUSCATED, ids=[f"obf-{i}" for i in range(len(_OBFUSCATED))]
)
def test_obfuscated_url_schemes_rejected(html: str, attr: str) -> None:
    result = sanitize_html(html)
    assert "javascript:" not in result.lower()
    assert attr not in result.lower()


@pytest.mark.parametrize(
    "void_html, must_present",
    [
        (
            '<input type="text" name="q"><p>Safe paragraph.</p>',
            "<p>Safe paragraph.</p>",
        ),
        ('<embed src="evil.swf"><p>Safe paragraph.</p>', "<p>Safe paragraph.</p>"),
        (
            '<meta http-equiv="refresh" content="0;url=evil"><p>Safe.</p>',
            "<p>Safe.</p>",
        ),
        (
            '<input type="text"><meta name="x"><link rel="x"><p>Survives all three.</p>',
            "<p>Survives all three.</p>",
        ),
    ],
    ids=["input", "embed", "meta", "cascade"],
)
def test_void_dangerous_tags_dont_suppress_siblings(
    void_html: str, must_present: str
) -> None:
    result = sanitize_html(void_html)
    for tag in ("input", "embed", "meta", "link", "base", "frame"):
        assert f"<{tag}" not in result.lower()
    assert must_present in result


def test_gfm_task_list_preserves_list_structure() -> None:
    html = (
        "<ul>"
        '<li><input checked="" disabled="" type="checkbox"> Task one</li>'
        '<li><input disabled="" type="checkbox"> Task two</li>'
        "</ul>"
    )
    result = sanitize_html(html)
    assert "<input" not in result.lower()
    assert "<ul>" in result and "<li>" in result and "</ul>" in result
    assert "Task one" in result and "Task two" in result


def test_mixed_safe_and_unsafe() -> None:
    html = (
        "<p>Text with <strong>bold</strong>.</p>"
        "<script>alert(1)</script>"
        '<img src="https://example.com/img.png" alt="pic" />'
        '<a href="javascript:alert(1)">bad</a>'
        "<blockquote><p>Quote</p></blockquote>"
    )
    result = sanitize_html(html)
    assert "<strong>bold</strong>" in result
    assert "<script" not in result.lower()
    assert 'src="https://example.com/img.png"' in result
    assert "javascript:" not in result.lower()
    assert "<blockquote>" in result
