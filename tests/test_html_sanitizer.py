"""Tests for the allowlist-based HTML sanitizer.

The sanitizer runs after Markdown rendering and after front-matter removal.
It preserves normal paragraphs, headings, lists, tables, images, links,
quotes, emphasis, and code while removing scripts, styles, iframes, objects,
embeds, forms, event-handler attributes, and dangerous URL schemes.

The sanitizer uses only stdlib (``html.parser.HTMLParser``) and no new
dependencies.
"""

from __future__ import annotations

from github_blog.utils.html_sanitizer import sanitize_html


class TestSafeContentPreserved:
    """Ordinary Markdown-rendered HTML is preserved."""

    def test_paragraphs_preserved(self) -> None:
        html = "<p>Hello world.</p>"
        assert "<p>Hello world.</p>" in sanitize_html(html)

    def test_headings_preserved(self) -> None:
        html = "<h1>Title</h1><h2>Section</h2><h3>Sub</h3>"
        result = sanitize_html(html)
        assert "<h1>Title</h1>" in result
        assert "<h2>Section</h2>" in result
        assert "<h3>Sub</h3>" in result

    def test_lists_preserved(self) -> None:
        html = "<ul><li>one</li><li>two</li></ul>"
        assert "<ul><li>one</li><li>two</li></ul>" in sanitize_html(html)

    def test_ordered_list_preserved(self) -> None:
        html = "<ol><li>first</li><li>second</li></ol>"
        result = sanitize_html(html)
        assert "<ol>" in result
        assert "<li>first</li>" in result

    def test_table_preserved(self) -> None:
        html = (
            "<table><thead><tr><th>A</th></tr></thead>"
            "<tbody><tr><td>1</td></tr></tbody></table>"
        )
        result = sanitize_html(html)
        assert "<table>" in result
        assert "<th>A</th>" in result
        assert "<td>1</td>" in result

    def test_image_preserved(self) -> None:
        html = '<img src="https://example.com/img.png" alt="alt text" />'
        result = sanitize_html(html)
        assert "<img" in result
        assert 'src="https://example.com/img.png"' in result
        assert 'alt="alt text"' in result

    def test_link_preserved(self) -> None:
        html = '<a href="https://example.com">link</a>'
        result = sanitize_html(html)
        assert '<a href="https://example.com">link</a>' in result

    def test_blockquote_preserved(self) -> None:
        html = "<blockquote><p>Quote.</p></blockquote>"
        assert "<blockquote>" in sanitize_html(html)

    def test_emphasis_preserved(self) -> None:
        html = "<p><strong>bold</strong> and <em>italic</em></p>"
        result = sanitize_html(html)
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_code_preserved(self) -> None:
        html = "<p><code>inline code</code></p>"
        assert "<code>inline code</code>" in sanitize_html(html)

    def test_pre_code_block_preserved(self) -> None:
        html = '<pre><code class="language-python">print(1)\n</code></pre>'
        result = sanitize_html(html)
        assert "<pre>" in result
        assert "<code" in result
        assert "print(1)" in result

    def test_hr_preserved(self) -> None:
        assert "<hr" in sanitize_html("<hr/>")

    def test_br_preserved(self) -> None:
        assert "<br" in sanitize_html("<br/>")


class TestDangerousElementsRemoved:
    """Scripts, styles, iframes, objects, embeds, forms are stripped."""

    def test_script_removed(self) -> None:
        html = "<p>safe</p><script>alert('xss')</script>"
        result = sanitize_html(html)
        assert "<script" not in result.lower()
        assert "alert" not in result
        assert "<p>safe</p>" in result

    def test_style_removed(self) -> None:
        html = "<p>safe</p><style>body{color:red}</style>"
        result = sanitize_html(html)
        assert "<style" not in result.lower()
        assert "color:red" not in result

    def test_iframe_removed(self) -> None:
        html = '<p>safe</p><iframe src="https://evil.com"></iframe>'
        result = sanitize_html(html)
        assert "<iframe" not in result.lower()

    def test_object_removed(self) -> None:
        html = "<p>safe</p><object data='evil.swf'></object>"
        result = sanitize_html(html)
        assert "<object" not in result.lower()

    def test_embed_removed(self) -> None:
        html = "<p>safe</p><embed src='evil.swf'>"
        result = sanitize_html(html)
        assert "<embed" not in result.lower()

    def test_form_removed(self) -> None:
        html = "<p>safe</p><form action='evil.com'><input name='x'></form>"
        result = sanitize_html(html)
        assert "<form" not in result.lower()
        assert "<input" not in result.lower()

    def test_script_content_removed_not_just_tag(self) -> None:
        html = "<script>document.cookie</script><p>safe</p>"
        result = sanitize_html(html)
        assert "document.cookie" not in result
        assert "<p>safe</p>" in result


class TestDangerousAttributesRemoved:
    """Event-handler attributes are stripped from all elements."""

    def test_onclick_removed(self) -> None:
        html = '<p onclick="alert(1)">text</p>'
        result = sanitize_html(html)
        assert "onclick" not in result.lower()
        assert "<p>text</p>" in result

    def test_onerror_removed_from_img(self) -> None:
        html = '<img src="x" onerror="alert(1)" alt="a" />'
        result = sanitize_html(html)
        assert "onerror" not in result.lower()
        assert 'alt="a"' in result

    def test_onmouseover_removed(self) -> None:
        html = '<a href="https://example.com" onmouseover="alert(1)">link</a>'
        result = sanitize_html(html)
        assert "onmouseover" not in result.lower()
        assert 'href="https://example.com"' in result


class TestDangerousUrlSchemesRemoved:
    """Unsafe URL schemes in href and src are neutralized."""

    def test_javascript_scheme_removed_from_href(self) -> None:
        html = '<a href="javascript:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_javascript_scheme_removed_from_src(self) -> None:
        html = '<img src="javascript:alert(1)" alt="x" />'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_data_scheme_removed_from_href(self) -> None:
        html = '<a href="data:text/html,<script>alert(1)</script>">x</a>'
        result = sanitize_html(html)
        assert "data:" not in result.lower()

    def test_vbscript_scheme_removed(self) -> None:
        html = '<a href="vbscript:msgbox(1)">x</a>'
        result = sanitize_html(html)
        assert "vbscript:" not in result.lower()

    def test_safe_http_link_preserved(self) -> None:
        html = '<a href="https://example.com">link</a>'
        assert 'href="https://example.com"' in sanitize_html(html)

    def test_safe_relative_link_preserved(self) -> None:
        html = '<a href="/page/">link</a>'
        assert 'href="/page/"' in sanitize_html(html)

    def test_safe_anchor_link_preserved(self) -> None:
        html = '<a href="#section">link</a>'
        assert 'href="#section"' in sanitize_html(html)

    def test_safe_mailto_preserved(self) -> None:
        html = '<a href="mailto:user@example.com">email</a>'
        assert 'href="mailto:user@example.com"' in sanitize_html(html)


class TestComplexContent:
    def test_mixed_safe_and_unsafe(self) -> None:
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

    def test_github_pasted_image_preserved(self) -> None:
        """GitHub user-content images are safe and must be preserved."""
        html = (
            '<img src="https://github.com/user-attachments/assets/abc123.png" '
            'alt="Screenshot" />'
        )
        result = sanitize_html(html)
        assert "github.com/user-attachments/assets/abc123.png" in result
        assert "<img" in result

    def test_nested_safe_elements_preserved(self) -> None:
        html = "<div><p>Nested <em>text</em>.</p></div>"
        result = sanitize_html(html)
        assert "<em>text</em>" in result

    def test_empty_string_returns_empty(self) -> None:
        assert sanitize_html("") == ""

    def test_plain_text_preserved(self) -> None:
        assert sanitize_html("just text") == "just text"


class TestEntityDecodedInjection:
    """Entity-decoded content must not produce live HTML tags.

    With ``convert_charrefs=True`` the parser decodes ``&lt;`` to ``<`` in
    the data stream.  Without re-escaping, this would inject live tags.
    """

    def test_entity_decoded_script_tag_neutralized(self) -> None:
        """``&lt;script&gt;`` decodes to ``<script>`` in data; must be re-escaped."""
        html = "&lt;script&gt;alert(1)&lt;/script&gt;"
        result = sanitize_html(html)
        assert "<script" not in result.lower()
        # The text is preserved as visible text, not as a live tag.
        assert "&lt;script&gt;" in result

    def test_entity_decoded_img_tag_neutralized(self) -> None:
        html = "&lt;img src=x onerror=alert(1)&gt;"
        result = sanitize_html(html)
        assert "<img" not in result.lower()

    def test_entity_decoded_text_preserved_as_text(self) -> None:
        """Decoded entities in text are re-escaped and displayed as text."""
        html = "&lt;b&gt;not bold&lt;/b&gt;"
        result = sanitize_html(html)
        assert "<b>" not in result
        assert "&lt;" in result

    def test_entity_decoded_iframe_neutralized(self) -> None:
        html = "&lt;iframe src='javascript:alert(1)'&gt;&lt;/iframe&gt;"
        result = sanitize_html(html)
        assert "<iframe" not in result.lower()


class TestAttributeQuoteEscaping:
    """Attribute values must be quote-escaped to prevent breakout."""

    def test_quote_in_alt_value_escaped(self) -> None:
        html = '<img src="x" alt="a&quot; onmouseover=&quot;alert(1)" />'
        result = sanitize_html(html)
        # onmouseover must not appear as a live (unquoted) attribute.
        assert 'onmouseover="' not in result.lower()
        assert "onmouseover='" not in result.lower()

    def test_quote_in_href_value_escaped(self) -> None:
        html = '<a href="https://example.com&quot; onclick=&quot;alert(1)">link</a>'
        result = sanitize_html(html)
        assert 'onclick="' not in result.lower()
        assert "onclick='" not in result.lower()

    def test_quote_in_title_value_escaped(self) -> None:
        html = '<a href="https://example.com" title="test&quot; onmouseover=&quot;alert(1)">link</a>'
        result = sanitize_html(html)
        assert 'onmouseover="' not in result.lower()
        assert "onmouseover='" not in result.lower()

    def test_single_quote_breakout_escaped(self) -> None:
        html = "<img src='x' alt='a' onmouseover='alert(1)' />"
        result = sanitize_html(html)
        assert "onmouseover" not in result.lower()


class TestObfuscatedUrlSchemes:
    """URLs with obfuscation characters must be rejected before scheme check."""

    def test_tab_in_javascript_scheme_rejected(self) -> None:
        html = '<a href="java\tscript:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()
        assert "href" not in result.lower() or "java" not in result.lower()

    def test_newline_in_javascript_scheme_rejected(self) -> None:
        html = '<a href="java\nscript:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_carriage_return_in_javascript_scheme_rejected(self) -> None:
        html = '<a href="java\rscript:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_line_separator_in_javascript_scheme_rejected(self) -> None:
        html = '<a href="java\u2028script:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_paragraph_separator_in_javascript_scheme_rejected(self) -> None:
        html = '<a href="java\u2029script:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_zero_width_space_in_javascript_scheme_rejected(self) -> None:
        html = '<a href="java\u200bscript:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()

    def test_control_char_in_img_src_rejected(self) -> None:
        html = '<img src="java\tscript:alert(1)" alt="x" />'
        result = sanitize_html(html)
        assert "javascript:" not in result.lower()
        assert "src" not in result.lower() or "java" not in result.lower()

    def test_safe_url_without_obfuscation_preserved(self) -> None:
        html = '<a href="https://example.com/path?q=1">link</a>'
        result = sanitize_html(html)
        assert "https://example.com/path?q=1" in result


class TestDangerousVoidTagsDontSuppressSiblings:
    """Dangerous void tags (input, embed, meta, link, base, frame) must be
    dropped themselves without suppressing following safe content.

    Void elements have no closing tag, so incrementing suppress depth would
    swallow all subsequent siblings.  Dangerous container tags (script,
    style, iframe, …) still suppress their content.
    """

    def test_gfm_task_list_input_does_not_suppress_text(self) -> None:
        """GFM task-list renders <input> inside <li>; following text must survive."""
        # Use the exact form marko generates: non-self-closing <input>.
        html = (
            "<ul>"
            '<li><input checked="" disabled="" type="checkbox"> Task one</li>'
            '<li><input disabled="" type="checkbox"> Task two</li>'
            "</ul>"
        )
        result = sanitize_html(html)
        assert "<input" not in result.lower()
        assert "Task one" in result
        assert "Task two" in result

    def test_standalone_input_followed_by_safe_content(self) -> None:
        # Non-self-closing form (void element without />).
        html = '<input type="text" name="q"><p>Safe paragraph.</p>'
        result = sanitize_html(html)
        assert "<input" not in result.lower()
        assert "<p>Safe paragraph.</p>" in result

    def test_embed_followed_by_safe_content(self) -> None:
        html = '<embed src="evil.swf"><p>Safe paragraph.</p>'
        result = sanitize_html(html)
        assert "<embed" not in result.lower()
        assert "<p>Safe paragraph.</p>" in result

    def test_meta_followed_by_safe_content(self) -> None:
        html = '<meta http-equiv="refresh" content="0;url=evil"><p>Safe.</p>'
        result = sanitize_html(html)
        assert "<meta" not in result.lower()
        assert "<p>Safe.</p>" in result

    def test_link_followed_by_safe_content(self) -> None:
        html = '<link rel="stylesheet" href="evil.css"><p>Safe.</p>'
        result = sanitize_html(html)
        assert "<link" not in result.lower()
        assert "<p>Safe.</p>" in result

    def test_base_followed_by_safe_content(self) -> None:
        html = '<base href="https://evil.com/"><p>Safe.</p>'
        result = sanitize_html(html)
        assert "<base" not in result.lower()
        assert "<p>Safe.</p>" in result

    def test_frame_followed_by_safe_content(self) -> None:
        html = '<frame src="evil.html"><p>Safe.</p>'
        result = sanitize_html(html)
        assert "<frame" not in result.lower()
        assert "<p>Safe.</p>" in result

    def test_multiple_void_dangerous_tags_dont_cascade(self) -> None:
        """Multiple dangerous void tags in sequence must not accumulate depth."""
        html = (
            '<input type="text"><meta name="x"><link rel="x"><p>Survives all three.</p>'
        )
        result = sanitize_html(html)
        assert "<input" not in result.lower()
        assert "<meta" not in result.lower()
        assert "<link" not in result.lower()
        assert "<p>Survives all three.</p>" in result

    def test_dangerous_container_still_suppresses_content(self) -> None:
        """Container dangerous tags (script, iframe) still suppress their content."""
        html = "<script>alert(1)</script><p>Safe.</p>"
        result = sanitize_html(html)
        assert "alert" not in result
        assert "<p>Safe.</p>" in result

    def test_input_inside_list_item_preserves_list_structure(self) -> None:
        """Full GFM task-list rendering must keep <ul>/<li> structure intact."""
        html = (
            "<ul>"
            '<li><input checked="" disabled="" type="checkbox">First task</li>'
            '<li><input disabled="" type="checkbox">Second task</li>'
            "</ul>"
        )
        result = sanitize_html(html)
        assert "<input" not in result.lower()
        assert "<ul>" in result
        assert "<li>" in result
        assert "First task" in result
        assert "Second task" in result
        assert "</ul>" in result
