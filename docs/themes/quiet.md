# Quiet

Quiet is the built-in Theme: neutral black and white with a few avatar-magenta
accents.

## Using Quiet

```yaml
theme:
  use: quiet
```

This is the default; a Config without `theme` uses Quiet. To change some of
Quiet's templates or styles, see [Extend Quiet](authoring.md#2-extend-quiet).

Quiet has a template for every kind of page. When `pages` in `config.yaml`
turns a page off (`pages.tags: false`) or moves it (`pages.blog: /posts/`),
Quiet hides links to pages that are off; see [Pages](../site-inputs.md#pages).
Quiet also works for a site under a path, such as
`https://alice.github.io/notes/`.

## Options

Set them under `theme.options` in `config.yaml`:

```yaml
theme:
  options:
    tagline: Researcher / tool builder
    featured_posts: [41, 62]
    accent_color: "#2f6aa7"
```

| Option | Type | Default | What it does |
| --- | --- | --- | --- |
| `tagline` | string | empty | One line above the bio on Home |
| `featured_posts` | posts | `[]` | Blog Issue numbers listed under Featured on Home, in this order. A number that is not a published Blog post is left out with the warning `THEME_OPTION_POST_MISSING` |
| `footer_text` | string | empty | Footer text next to the author name; empty shows "Thanks for reading." in the site's language |
| `show_powered_by` | boolean | `true` | Show the "Powered by escaping" footer link |
| `accent_color` | color | empty | Accent color in light mode, such as `"#a72f6a"`; empty keeps Quiet's |
| `accent_color_dark` | color | empty | Accent color in dark mode, such as `"#e58bb6"`; empty keeps Quiet's |
| `comments_theme` | choice | `github-light` | Utterances colors used when `comments_theme_mode` is `fixed`: `github-light`, `github-dark`, `preferred-color-scheme`, `github-dark-orange`, `icy-dark`, `dark-blue`, `photon-dark`, `boxy-light` or `gruvbox-dark` |
| `comments_theme_mode` | choice | `auto` | `auto` follows Quiet's light or dark mode; `fixed` always uses `comments_theme` |

Quote colors: YAML treats everything after an unquoted `#` as a comment. A
misspelt option name or an invalid value fails the build and names the option.
Comments are off by default; see [Comments](authoring.md#comments) to turn
them on.

## Interface language

Quiet's interface text comes in English (`en`) and Chinese (`zh`), chosen by
`site.language`: `zh`, `zh-CN`, `zh-TW` and any other language starting with
`zh` get Chinese; every other language gets English. Titles and text of posts
are shown as written in the Issues.

To change one piece of interface text, override its key in a Theme that
extends Quiet:

```yaml
api: 4
extends: quiet
strings:
  en:
    search_placeholder: Search the notes…
  zh:
    search_placeholder: 搜索笔记…
```

Keep any `{name}` placeholder in the text, such as `{count}` in
`search_count`; Quiet fills it in. The English and Chinese wording of every
key is in Quiet's
[`theme.yaml`](../../src/escaping/themes/quiet/theme.yaml). The keys, by
where they appear:

| Where | Keys |
| --- | --- |
| Page frame and menu | `skip_to_content`, `home`, `menu`, `toggle_menu`, `dark_mode`, `site_index`, `main_navigation`, `rail_note`, `back_home`, `back_to_section`, `back_to_top` |
| Search | `search`, `search_placeholder`, `search_label`, `search_scope`, `search_close`, `search_retry`, `search_results`, `search_select_hint`, `search_close_hint`, `browse_blog`, `browse_tags`, `search_loading`, `search_failed`, `search_empty`, `search_no_results`, `search_browse`, `search_count_one`, `search_count`, `search_truncated` |
| Footer | `footer_thanks`, `footer_links`, `powered_by` |
| Home | `featured`, `recent_articles`, `all_articles`, `no_writing_yet`, `my_projects`, `all_projects`, `home_intro`, `home_intro_blog`, `home_intro_projects`, `home_intro_about` |
| Blog and Tags | `blog`, `blog_eyebrow`, `blog_caption`, `explore_by_topic`, `blog_pagination`, `newer`, `older`, `empty_writing`, `tags`, `tags_eyebrow`, `tags_caption`, `tags_empty`, `tags_label`, `related_articles` |
| Ideas | `ideas`, `ideas_eyebrow`, `ideas_caption`, `ideas_empty_title`, `ideas_empty_body`, `explore_writing` |
| About and Projects | `about`, `also_building`, `projects`, `projects_eyebrow`, `projects_caption`, `projects_empty`, `website`, `links_for` |
| Articles | `discuss`, `article_navigation`, `previous`, `next`, `on_this_page`, `copy_code`, `copied`, `copy_failed` |
| Comments | `conversation`, `comments_intro`, `comments_loading`, `comments_noscript`, `comments_unavailable`, `comments_view_on_github` |
| Not found | `not_found`, `not_found_body` |

## Files you can replace

A file with the same name in a Theme that extends Quiet replaces Quiet's. These
files are split out for that purpose:

| File | Contents |
| --- | --- |
| `head-extra.html` | Empty; placed at the end of every page's `<head>`. For analytics, fonts or another stylesheet |
| `home-intro.html` | The introduction under the title on Home: `tagline`, `profile.bio` and one sentence linking the Blog, Projects and About |
| `header.html` | The buttons at the top right of Home and the sidebar of other pages (avatar, menu, search, dark mode switch) |
| `footer.html` | The footer: author name, `footer_text`, `profile.links`, RSS and "Powered by" |
| `search.html` | The search dialog |
| `components.html` | Shared macros: tags, post lists, project cards, comments, Mermaid loading |
| `base.html` | The frame and `<head>` of every page. Replacing it affects every page |
| `static/css/style.css` and others | Static files are replaced by path too, such as `static/images/favicon.png` |

`@quiet/` reuses Quiet's original in your own file, for example
`{% extends "@quiet/home.html" %}`. A page template can set `page_title`,
`page_description` and `active_section`; `base.html` uses them for the title,
the description and the current menu item. See
[Reusing the file you replace](authoring.md#reusing-the-file-you-replace).

## Design notes

| Area | Behavior |
| --- | --- |
| Light | White canvas, near-black text, neutral gray sidebar and panels; links `#a72f6a` (change with `accent_color`) |
| Dark | Neutral near-black canvas, near-white text; links `#e58bb6` (change with `accent_color_dark`) |
| Accent | Magenta based on `#D2428A`, with lightness adjusted for AA contrast. Home shows `profile.avatar`; the sidebar on other pages shows the author's initials when there is no avatar |
| Home | One centered column, no sidebar. The introduction links the Blog, Projects and About. Below it: featured posts (`featured_posts`; hidden when not set), the 5 newest posts and up to 4 projects with `featured: true`. Post lists show title and date only; see [Featured writing on Home](../site-inputs.md#featured-writing-on-home) |
| Motion | Light CSS for the Home entrance, text links, the background tree shadows and project hover. With "reduce motion" set in the system, animation and movement stop. Without JavaScript, content and links work as usual |
| Blog | Archive titles 16px, summaries 14px, with dates and tags; no empty paragraph when a post has no summary. Tag pages show title, date and tags only |
| Reading | Other pages have a fixed sidebar, a table of contents for long posts, code copy buttons, a mobile menu, keyboard navigation and a fallback link when comments fail to load |
| Search | Home shows search and appearance buttons at the top right; other pages put search above the menu, and inside Menu on phones. The first open loads `search.json` and searches the titles, summaries and tags of published Blog posts, Ideas and projects (not the full text). Title matches rank above tags and summaries; every word must match; at most 20 results. Supports Ctrl/⌘ K, arrow keys, Tab and Esc, and returns focus to the button that opened it. If loading fails, readers can retry or go to the Blog or Tags. Without JavaScript, without the script, or without `<dialog>` support, the search button is hidden and the rest of the navigation works |
| Social preview | With `seo.social_image`, every page has `og:image` and `twitter:image` with the card type `summary_large_image`; a non-empty `seo.social_image_alt` adds both `*:image:alt` tags. Without it the card type is `summary` and there are no image tags |
| Navigation | The default menu is in [Missing-field sources](../site-inputs.md#missing-field-sources); Ideas has to be added. A custom menu replaces the default one; with an empty menu there is no Menu button, and the avatar and appearance switch stay |
| Comments | Off by default. Turn them on with `comments.enabled: true` and install the Utterances app on the repository. `comments_theme` and `comments_theme_mode` pick the colors. An About page made from the profile has no comments |
| Idea tags | Plain text, not links, because Ideas have no tag pages; Blog tags link to their tag page |
| End of a post | Blog posts end with "Previous" (newer) and "Next" (older) across all published Blog posts; the first and last show one side only. Ideas and About have none |
| Mermaid | Uses the `neutral` colors. Dark mode inverts the SVG only and print restores it, without rendering again; node borders have at least 3:1 contrast |
| Mobile menu | The menu does not depend on the reading scripts and does not move off the page after the first screen. Without JavaScript, or when `appearance.js` fails, the menu stays open; when `site.js` fails, the menu still opens and Esc closes it and returns focus to the button |
| Compact contents | At widths up to 1160px, with JavaScript on and h1–h3 in the post, space is kept for the table of contents; none without headings, without JavaScript, or in print. Known limits: a failed script leaves an empty space (but no button that cannot be clicked); HTML that loads in parts may still shift; browsers without `:has()` or `scripting` show the contents a little later |
| Appearance choice | A reader's light or dark choice is kept in `localStorage` under `quiet-theme` |
| Print | Black on white; content images keep their colors, SVGs use neutral light colors |

Quiet's Mermaid colors suit its neutral diagrams. Check the meaning and
contrast of your own `classDef` colors, color images and third-party content.
The comments and Mermaid scripts are shared by every Theme; see
[Static and shared assets](authoring.md#static-and-shared-assets).
