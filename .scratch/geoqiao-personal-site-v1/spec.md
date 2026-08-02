# geoqiao.me Personal Site v1

Status: ready-for-agent

## Problem Statement

当前 `escaping` 将 PyGithub Issue 对象直接传递到编排、渲染和模板层，内容选择、labels、URL、Markdown 与页面生成规则彼此耦合。现有实现仍从标题生成旧 `.html` slug、把所有 labels 当作 tags，并在完整验证前删除输出目录，无法安全实现已经确定的 Blog、Idea、About、Projects、主题和 Pages Artifact 架构。

作者还需要一个极轻量的 Local Draft 上传入口，但不需要本地同步系统。GitHub Issue 必须在创建后成为唯一内容权威来源；`escaping` 必须保持为只读的 Site Compiler，不能承担上传、认证状态或 Issue mutation。

目标是在不引入数据库、运行时插件、双向同步或多版本 parser 的前提下，将 `escaping` 重构成一个严格、可测试、可复用的静态站点编译器，并用于生成新的 `geoqiao.me` 个人站。

## Solution

作者可以继续使用本地 Markdown 或 GitHub UI 写作：Local Draft 通过一次性 Uploader 变成未发布 Issue，之后所有编辑和发布都在 GitHub 完成。Blog、Idea 和 About 使用同一套明确格式；Projects 和 Site Profile 由站点仓库维护。访问者获得统一 URL、完整 Tags、Blog-only Atom、项目目录和安全渲染的页面。

构建时，`escaping` 只读取内容并一次性报告全部错误。未发布草稿不会影响正式站点，错误的已发布内容不会覆盖当前正常产物。通过验证的内容生成完整静态站，再由 GitHub Actions 部署 Pages Artifact。历史 Issues 在正式切换前手工更新；系统不保留第二套 parser 或同步状态。

实现上，Site Compiler 使用一次构建期间的内部内容模型隔离 GitHub、内容规则与主题，确保 YAML 不进入正文、URL 来自同一来源、模板不依赖 PyGithub。这些内部结构服务于上述用户行为，不形成新的内容权威来源。

## User Stories

1. As the site author, I want to write a Blog as a local Markdown draft, so that I can use my preferred local editor.
2. As the site author, I want a Local Draft to contain only the agreed authoring fields and Markdown body, so that the format remains easy to understand.
3. As the site author, I want the Issue Draft Uploader to validate every required field before uploading, so that malformed drafts do not become Issues.
4. As the site author, I want the Uploader to preserve my Markdown body unchanged, so that images, links, code blocks, and formatting are not rewritten.
5. As the site author, I want the Uploader to create missing type and tag labels, so that upload does not fail merely because a label has not been initialized.
6. As the site author, I want the Uploader to create a new unpublished Issue, so that uploading does not make content visible on the site.
7. As the site author, I want the Uploader to use my existing GitHub CLI authentication, so that credentials are not stored in drafts or repository files.
8. As the site author, I want the Uploader to report the created Issue number and URL, so that I can continue editing in GitHub.
9. As the site author, I want the Local Draft to have no role after upload, so that I do not need to understand synchronization or conflict resolution.
10. As the site author, I want GitHub Issue Content to become the sole authority after creation, so that direct GitHub editing remains simple.
11. As the site author, I want to publish and unpublish content using the `published` label, so that Issue open/closed state does not control the website.
12. As the site author, I want unfinished unpublished Issues to be ignored without YAML validation, so that remote drafts cannot break the production build.
13. As the site author, I want malformed published content to stop deployment, so that broken pages are never silently shipped.
14. As the site author, I want every validation error reported in one run, so that I can fix all affected Issues together.
15. As the site author, I want Issues from unapproved authors ignored with a warning, so that other repository users cannot publish to my site.
16. As the site author, I want direct manual GitHub authoring to remain possible, so that the Uploader is optional.
17. As the site author, I want YAML metadata removed before Markdown rendering, so that development metadata never appears in the visible article body.
18. As the site author, I want Blog and Idea content to preserve their authored `created_date`, so that visitors can see when the content itself was created.
19. As the site author, I want Issue `created_at` to remain the publication timestamp and collection ordering key, so that date semantics stay consistent.
20. As the site author, I want About to display no date, so that it reads as a timeless profile page.
21. As the site author, I want Blog tags to generate the public `/tags/` taxonomy, so that Blog content can be browsed by topic.
22. As the site author, I want Idea tags displayed with each Idea but excluded from `/tags/`, so that Idea metadata does not change the Blog taxonomy.
23. As the site author, I want About to reject tags, so that it remains a singleton profile page rather than categorized content.
24. As a visitor, I want Blog canonical URLs to use `/blog/{slug}/`, so that new article URLs are readable and stable.
25. As a visitor, I want Idea canonical URLs to use the immutable Issue number, so that Idea links remain stable without local slugs.
26. As a visitor, I want About to use `/about/`, so that its URL is independent of the Issue title.
27. As a visitor, I want `/tags/` and `/tags/{tag}/` to be generated consistently, so that tag navigation does not depend on template-specific URL strings.
28. As a visitor, I want Home to present the site identity and recent Blog content, so that I can quickly understand the author and discover new writing.
29. As a visitor, I want Ideas presented as independent short records with their own detail pages, so that each Idea has a stable identity and discussion thread.
30. As a visitor, I want the Projects page to show a curated catalog rather than every GitHub repository, so that the page reflects author intent.
31. As a visitor, I want Project API enrichment failures to degrade gracefully, so that missing stars or language data does not break the whole site.
32. As a visitor, I want the About page to combine reusable profile identity with a detailed Issue-authored narrative, so that concise and long-form profile content have clear ownership.
33. As a visitor, I want comments bound to immutable Issue numbers, so that title, slug, and domain changes do not split discussions.
34. As a feed subscriber, I want the main Atom feed to remain Blog-only, so that its existing content meaning does not unexpectedly change.
35. As a feed subscriber, I want entry publication and update timestamps derived consistently from GitHub timestamps, so that feed readers order entries correctly.
36. As a search engine, I want canonical, sitemap, feed, Open Graph, and internal URLs derived from one RouteRegistry, so that the site never publishes conflicting URLs.
37. As a visitor, I want pasted GitHub images and normal Markdown to render correctly, so that ordinary authoring remains convenient.
38. As a visitor, I want dangerous scripts, event handlers, embedded objects, forms, and unsafe URL schemes removed from Issue Markdown, so that viewing the static site is safe.
39. As a theme author, I want templates to consume stable internal content models, so that themes do not depend on PyGithub implementation details.
40. As the maintainer, I want Escape1 and Escape2 migrated to the same SiteModel interface, so that the parser refactor does not create theme-specific content rules.
41. As the maintainer, I want the future geoqiao.me theme pinned by immutable commit, so that builds never upgrade theme code implicitly.
42. As the maintainer, I want site overrides to take precedence over the locked theme, so that personal customization does not fork the compiler.
43. As the maintainer, I want configuration fields validated strictly, so that misspelled or unknown settings fail instead of being ignored.
44. As the maintainer, I want Settings injected explicitly into compiler and rendering modules, so that tests and builds do not depend on global configuration.
45. As the maintainer, I want GitHub API access isolated behind an adapter, so that PyGithub changes do not spread through the compiler and themes.
46. As the maintainer, I want core modules to return diagnostics rather than call `sys.exit`, so that behavior can be tested through module interfaces.
47. As the maintainer, I want the current valid output preserved when a new build fails, so that a content mistake cannot replace the deployed site with partial output.
48. As the maintainer, I want complete artifact validation before replacement, so that HTML, XML, links, assets, canonical URLs, and routes are checked as one site.
49. As the maintainer, I want GitHub Actions to deploy a Pages Artifact from the site repository, so that generated HTML is not committed back to a deployment branch.
50. As the maintainer, I want a single strict cutover after historical Issues are migrated, so that old and new parsers do not coexist indefinitely.
51. As the maintainer, I accept dropping historical `.html` Blog URLs without redirects, so that the route implementation has no alias or migration machinery.
52. As an open-source user of `escaping`, I want personal site configuration, authoring tools, and deployment credentials kept outside the compiler, so that the compiler remains reusable.
53. As the site author, I want an invalid configured About Issue to fail the build, so that `/about/` never silently disappears or uses the wrong content.
54. As a visitor, I want the Blog archive paginated with stable trailing-slash routes, so that large archives remain navigable.
55. As a visitor, I want valid empty states for Blog, Ideas, Projects, Tags, and Atom, so that a new or partially configured site still builds coherently.
56. As a visitor, I want Home to show exactly the five most recently published Blog posts, so that the landing page stays focused.
57. As a visitor, I want Utterances to follow the active light or dark theme and load reliably in Safari, so that comments remain usable after theme migration.
58. As the maintainer, I want dangerous output paths rejected before deletion or rendering, so that a configuration error cannot remove unrelated files.
59. As the maintainer, I want the Pages workflow to use least-privilege permissions and short-lived GitHub credentials, so that deployment does not depend on a personal PAT.
60. As a search engine, I want `https://geoqiao.me` to be the only canonical origin with consistent structured metadata, so that indexing signals are not split.
61. As the maintainer, I want the complete Issue Content and Local Draft contracts treated as normative acceptance criteria, so that implementation tickets cannot silently omit a MUST requirement.

## Implementation Decisions

### Normative sources

- The accepted Issue Content Contract and Local Draft Contract are normative dependencies of this spec. Every MUST and MUST NOT in those contracts is part of implementation acceptance even when this spec only summarizes the rule.
- Accepted ADRs governing responsibility separation, one-way Local Draft creation, and dropping legacy `.html` URLs remain binding.
- This spec supersedes earlier research wherever later accepted contracts, ADRs, or explicit user decisions differ.

### Responsibility and dependency direction

- Issue Draft Uploader, Site Compiler, and Site Orchestrator remain separate responsibilities.
- The Uploader is a user-invoked Agent Skill, not an `escaping` command or synchronization subsystem.
- The repository-level Uploader Skill has already been authored and validated as a design-session asset. Its physical location is not part of the Site Compiler interface and creates no runtime dependency; future relocation or copying to the site repository is optional, not a compiler implementation ticket.
- The Site Compiler never creates, edits, labels, publishes, or unpublishes Issues.
- GitHub Actions is the Site Orchestrator and deploys a Pages Artifact from the site repository.
- Settings are explicitly injected. No global settings singleton will be introduced.

### Local Draft and Uploader

- Local Draft front matter allows only `title`, `type`, `slug`, `description`, `tags`, and `created_date`.
- `title`, `type`, `description`, `created_date`, and non-empty Markdown body are required for every content type.
- Blog requires `slug`; Idea and About forbid it.
- Blog and Idea allow optional `tags`; About forbids tags.
- `created_date` is a quoted `YYYY-MM-DD` string.
- The Uploader validates the Local Draft Contract, preserves the body unchanged, creates missing `type:*` and `tag:*` labels, and creates one new Issue without `published`.
- The Uploader uses an explicit target repository and existing `gh auth login` state. It does not request or persist credentials.
- The Uploader does not modify the Local Draft, create sidecars, store Issue numbers, retry ambiguous creates automatically, or update existing Issues.

### Single Issue Content format

- The runtime Issue format has no schema or version field. Only one current parser exists.
- Historical Issues must be manually edited to the current format before strict cutover.
- The Issue title is the content title; Issue number is identity and comment binding.
- Exactly one supported `type:*` label defines Blog, Idea, or About.
- The `published` label is the only publication gate. Open/closed state has no publication meaning.
- Blog and Idea may use `tag:*`; About may not.
- Idea tags may be displayed with Idea content but do not enter the Blog Tags taxonomy.
- Issue body front matter contains only `slug` when applicable, `description`, and `created_date`.
- YAML is parsed safely; the exact envelope, first-line and closing delimiters, mapping requirement, 16 KiB UTF-8 limit, duplicate-key and custom-tag rejection, and unknown-field rejection follow the complete Issue Content Contract.
- Type, author, tag, slug, description, route, normalization, length, plain-text, and collision rules follow the complete Issue Content Contract, including unknown `type:*` rejection, Unicode NFC normalization, case-insensitive author/label comparison, tag length 1–50, slug length 1–80, description length at most 300 Unicode code points, and dynamic reserved-route checks.
- Front matter is separated before Markdown rendering and can never appear in rendered HTML.
- Blog, Idea, and About require non-empty title, description, `created_date`, and Markdown body.

### Selection and validation

- The GitHub adapter fetches open and closed Issues.
- Pull Requests are excluded before content parsing.
- Allowed authors come from strict site configuration.
- Unauthorized authors produce warnings and are ignored.
- Issues without `published` are ignored without parsing or validating their body.
- Published Issues from allowed authors are validated strictly.
- The configured About Issue is a required singleton exception to normal ignore behavior: if it is missing, a Pull Request, unauthorized, unpublished, incorrectly typed, duplicated by another valid published About, or otherwise invalid, the build fails.
- All detectable content validation errors are accumulated and reported in one run.
- Any error prevents rendering and output replacement; warnings do not.
- Diagnostics carry stable codes, severity, Issue number when applicable, field, and a human-readable message.
- Core modules return or raise structured build results; only the CLI maps final status to process exit codes.

### Internal compiler architecture

- The GitHub adapter is the only module that receives PyGithub objects.
- The adapter converts each external Issue into an immutable, in-memory IssueSnapshot containing only fields needed by the compiler.
- IssueSnapshot is not persisted and is not authoring or synchronization state.
- A deep SiteModelBuilder is the primary content seam. It owns selection, front matter parsing, field validation, type mapping, collection assembly, tags, singleton checks, and global route validation.
- The SiteModel contains explicit BlogPost, Idea, AboutPage, Project, Tag, and Route data rather than external GitHub objects.
- Common content fields use composition or straightforward dataclass fields; a complex inheritance hierarchy is not required.
- Templates never parse YAML, interpret labels, generate slugs, or access PyGithub attributes.

### Configuration contract

- Site configuration is repository-owned and rejects unknown fields at every nested level.
- Content selection configuration requires a non-empty `allowed_authors` list. About configuration requires immutable `issue_number` selection.
- Top-level site identity configuration provides title, author/display name, canonical origin, description, language, and navigation. Site Profile separately contains only avatar, short bio, and links.
- Page configuration provides Blog archive page size as a positive integer with default 10; Home recent Blog count is fixed at 5 for v1.
- Comment configuration provides provider, repository fallback, theme, and `theme_mode`, preserving `auto` behavior.
- Project Catalog data and theme lock are separate repository-owned inputs with their own strict fields; they are not embedded into Issue Content.
- Security configuration continues to name the token environment variable dynamically; implementation must not hard-code `G_T`.

### Date semantics

- `created_date` records the authored content creation date.
- Issue `created_at` is the publication timestamp and ordering key for Blog and Idea collections.
- Blog and Idea render `created_date`; About renders no date.
- Feed entry `published` uses Issue `created_at`; entry and feed update values use Issue `updated_at` according to the Issue Content Contract.
- Blog and Idea ties on Issue `created_at` sort by Issue number descending.
- Atom includes `rel="self"`. When Blog is empty, the feed remains valid and uses build start time as its feed-level updated value.

### Routes and page model

- RouteRegistry is the sole source for canonical URLs, internal links, sitemap entries, feed URLs, Open Graph URLs, and output paths.
- Home uses `/`; Blog archive uses `/blog/`; Blog detail uses `/blog/{slug}/`; Ideas index uses `/ideas/`; Idea detail uses `/ideas/{issue_number}/`; About uses `/about/`; Projects uses `/projects/`; Tags index and archives use `/tags/` and `/tags/{tag}/`; Atom uses `/atom.xml`; sitemap uses `/sitemap.xml`; robots uses `/robots.txt`.
- Blog archive page one is `/blog/`. Additional archive pages use `/blog/page/{number}/` for page numbers starting at 2. Page size is strict configuration with a default of 10.
- Trailing-slash page routes map to directory `index.html` outputs; file routes such as Atom retain their filename.
- Canonical paths are Unicode NFC-normalized and compared case-folded. The reserved-route set is derived from every registered site page rather than maintained as a separate static Issue-route list.
- Blog slugs are lower-case ASCII kebab-case and unique in the current snapshot. Keeping a slug frozen after first publication is an authoring lifecycle responsibility; the stateless compiler does not claim to detect historical changes without a publication ledger.
- Historical `.html` Blog URLs are dropped without aliases or redirects. Broken old links and possible SEO loss are accepted.
- Title-derived slugs, `.html` route assembly, template URL concatenation, and the separate `issue_slugs` map are removed.

### Site Profile, About, Ideas, and Projects

- Site Profile is repository-owned structured identity data containing only avatar, short bio, and links for Home and shared presentation. Home Hero uses top-level site identity, Site Profile, and configured navigation links as its text and CTA authority; it does not introduce a second long-form Home content source.
- Home displays exactly the five Blog posts with the newest Issue `created_at`; it may additionally display two or three Project Catalog entries marked featured without displacing the Hero.
- About Issue Content owns the detailed narrative and expertise. The About page may combine Site Profile identity with Issue Markdown.
- About is selected by configured immutable Issue number and must be the only valid published About Issue.
- One Idea maps to one Issue and has its own stable detail route and comment thread.
- Project catalog entries are repository-owned curated data. Each entry requires `slug`, `title`, `repository`, and `summary`, and supports `featured` plus numeric `order`. Entries sort deterministically by `order`, then slug. v1 links cards to GitHub and does not generate project detail pages.
- GitHub project metadata is optional enrichment for stars, forks, language, and topics. Optional `fallback_metadata` may provide non-negative `stars` and `forks`, a `language` string, and a list of `topics`; enrichment failure uses these values when present or omits the corresponding dynamic values and cannot fail the site build.
- Empty Blog, Ideas, Projects, and Tags collections still generate valid index pages with intentional empty states.

### Rendering and security

- SiteRenderer consumes SiteModel only.
- Markdown conversion follows GitHub-Flavored Markdown or a documented compatible subset. Allowlist sanitization happens after Markdown rendering and after Issue front matter has been removed.
- Normal Markdown paragraphs, headings, lists, tables, images, links, quotations, emphasis, and code remain supported.
- Scripts, styles, iframes, objects, embeds, forms, event-handler attributes, and unsafe URL schemes are removed or rejected from authored body HTML.
- Template-owned Utterances integration remains permitted and continues binding by Issue number. Theme migration preserves `theme_mode: auto` synchronization through `postMessage` and `MutationObserver`, and preserves the Safari compatibility behavior that removes lazy loading from the injected Utterances iframe.
- Escape1 and Escape2 migrate together to the SiteModel interface before visual redesign.
- The v1 geoqiao.me theme adopts the currently configured Escape2 visual language as its initial baseline. A new visual prototype or redesign is not required for v1; broader visual optimization is deferred until the core compiler and page behavior are stable.
- The separate geoqiao.me theme is included in this v1 scope after the existing themes are migrated. It is declarative, locked to a full immutable commit, and contains no executable Python extension.
- Theme builds resolve site overrides before the locked theme. The lock records repository, full commit, and theme API version. Build uses the locked commit from cache or fetches that exact commit when absent; upgrades happen only through an explicit theme update operation.
- Theme manifest validation covers API version, capabilities, required templates, and asset directories. Jinja uses StrictUndefined for theme contract enforcement.
- Escape1, Escape2, and the v1 geoqiao.me theme all satisfy the same content, route, comments, sanitization, and template-context acceptance matrix.

### Output and deployment

- The compiler completes fetch, parsing, validation, SiteModel construction, and RouteRegistry validation before rendering.
- Rendering targets a temporary output directory.
- Artifact validation covers required pages, links, assets, XML, canonical URLs, and route consistency.
- Before any deletion or rendering, the configured output path must pass a containment safety check: it must be an allowed repository-relative output directory and must not identify the repository root, filesystem root, current working directory, a parent directory, or a symlink escape. Unsafe paths fail before mutation.
- Final output is replaced only after all validation succeeds; failed builds preserve the previous output.
- GitHub Pages deployment uses the official upload-pages-artifact and deploy-pages flow from the site repository. Repository Pages Settings must switch its publication source from the `main` branch root to GitHub Actions before cutover, and repository guidance that still describes branch-root publishing must be updated in the same migration.
- The workflow uses short-lived `GITHUB_TOKEN`, not a personal PAT, with least-privilege `contents: read`, `issues: read`, `pages: write`, and `id-token: write` permissions.
- Orchestration triggers on path-filtered site-repository pushes, Issue opened/edited/labeled/unlabeled/closed/reopened events, and manual workflow dispatch. It does not trigger on Issue comments.
- Comment changes do not trigger static rebuilds because comments are read live by the comment provider.
- The sole canonical origin is `https://geoqiao.me`. Canonical, sitemap, Atom, Open Graph, Twitter Card, and JSON-LD URLs use the same route/origin builder. Home/About emit Person or WebSite structured data; Blog detail emits BlogPosting.
- Deployment enables HTTPS for the custom domain and validates canonical output plus the old GitHub Pages host behavior without treating old `.html` paths as supported aliases.
- Development happens on a feature branch while production `main` remains stable. The feature branch integrates the strict parser directly and does not maintain a legacy `.html` pipeline or compatibility switch for intermediate commits. Before merge, parser, models, routes, themes, artifact validation, and migrated Issue Content are verified together as one complete cutover.

## Testing Decisions

### Lean testing policy

- `docs/agents/testing.md` is the normative execution guide for test scope and review cost.
- Development uses focused TDD: one failing test for a user-visible behavior or meaningful safety boundary, minimal implementation, passing test, then refactor. Test-only refactors first record a green baseline and do not manufacture artificial failures.
- Each behavior has one primary test owner. Parser, compiler, sanitizer, RouteRegistry, theme contract, GitHub adapter, output staging, and full-site integration do not repeat one another's complete matrices.
- Each feature Ticket defaults to 3–6 logical tests. Themes are parameterized. Coverage percentage, private helpers, getters, dataclass mechanics, exact mock calls, and theoretical mutation completeness are not acceptance goals.
- Every major content batch retains one real static-site tracer. Final confidence comes from generated artifacts, link/canonical/XML validation, and desktop/mobile browser smoke rather than mechanically expanding unit cases.
- Reviewer findings block only for realistic security, data-loss, broken-artifact, contract, build, or deployment failures. New tests should normally strengthen an existing scenario instead of adding another function.

### Required coverage domains

- Development follows the repository's focused TDD sequence: failing contract test, minimal implementation, passing test, then refactor.
- The primary test seam is SiteModelBuilder: concrete IssueSnapshot values and content policy go in; a SiteModel plus diagnostics comes out. These tests cover most content behavior without GitHub, templates, or filesystem I/O.
- SiteModelBuilder tests cover Pull Request exclusion, author allowlist behavior, unpublished Issue skipping, exact type-label cardinality including unknown types, normalization rules, Blog/Idea tags, About tag rejection, the complete YAML envelope and 16 KiB limit, unknown fields, duplicate keys, required fields, body extraction, `created_date`, field length and plain-text constraints, slug lifecycle limits, singleton About failure matrix, sorting, tag aggregation, and route collisions.
- Tests explicitly verify that unpublished malformed bodies are not parsed and do not produce diagnostics.
- Tests explicitly verify that front matter fields never reach Markdown body or rendered HTML.
- Tests verify that all detectable published-content errors are returned together rather than failing on the first Issue.
- The GitHub adapter is tested at its own external seam for `state=all` querying, Pull Request metadata, author/label normalization, timestamps, and conversion to IssueSnapshot.
- Renderer tests use real internal content models rather than MagicMock PyGithub Issues.
- Theme contract tests run against Escape1, Escape2, and the v1 geoqiao.me theme and verify that no theme accesses `issue.*`, labels, front matter, or an `issue_slugs` map.
- RouteRegistry tests verify Home, Blog archive/detail/pagination, Ideas index/detail, About, Projects, Tags, Atom, sitemap, robots, trailing slash, output-path mapping, NFC/case-folded duplicate detection, dynamic reserved-route collisions, sitemap membership, and feed URL consistency.
- Markdown security tests cover scripts, event attributes, unsafe schemes, raw iframes, normal links, code blocks, tables, and GitHub-pasted images.
- Feed tests verify Blog-only membership, Issue `created_at` publication values, Issue `updated_at` update values, description summaries, empty-feed validity, and route consistency.
- About tests verify immutable Issue selection, singleton enforcement, Site Profile composition, comment binding, and absence of visible dates.
- Idea tests verify required body, optional displayed tags, exclusion from Blog Tags and Atom, Issue-number routes, and visible `created_date`.
- Project tests verify required catalog fields, deterministic `order`/slug sorting, featured selection, typed fallback metadata, empty state, and graceful API-enrichment failure.
- SiteCompiler integration tests exercise source snapshots through SiteModel, rendering, artifact validation, and final output replacement.
- Output safety tests prove that root, repository-root, current-directory, parent-directory, and symlink-escape paths are rejected before mutation, and that a failed parse, render, or artifact validation leaves the previous output intact.
- End-to-end artifact tests parse generated HTML and XML, verify internal links and assets, and ensure canonical, Open Graph, sitemap, feed, and filesystem routes agree.
- Existing tests that only preserve PyGithub leakage or title-derived `.html` slugs are replaced rather than layered beneath the new seam.
- Prior art comes from the existing renderer tests for real template output, configuration tests for Pydantic validation, pagination tests for archive behavior, template-integrity tests shared by Escape1/Escape2, and CLI integration tests for generated artifacts; these are migrated to internal models rather than duplicated with PyGithub mocks.
- Empty-state tests cover Blog, Ideas, Projects, Tags, and the Atom feed.
- Utterances tests preserve Issue-number binding, `theme_mode: auto` postMessage/MutationObserver behavior, and the Safari lazy-loading workaround in Escape1, Escape2, and the v1 geoqiao.me theme.
- Workflow tests or static assertions cover target repository ownership, Pages Settings source migration to GitHub Actions, updated repository guidance, exact triggers, absence of `issue_comment`, minimum permissions, official Pages actions, and absence of PAT-based clone/push deployment.
- Final validation includes pytest, Ruff, formatter check, ty, template integrity tests, XML parsing, internal-link validation, and desktop/mobile browser smoke checks for Home, Blog, Ideas, Projects, About, and Tags.

## Out of Scope

- Bidirectional Local Draft and Issue synchronization.
- Local upload state, sidecars, Issue bindings, conflict detection, pull, merge, or force-update operations.
- An `escaping` upload, publish, or Issue mutation command.
- Runtime schema dispatch, multiple content parsers, legacy parser, migration manifest, or compatibility switch.
- Historical URL aliases, redirect pages, or `.html` compatibility.
- A database, CMS backend, SSR, serverless functions, or incremental build state machine.
- Runtime Python theme plugins or arbitrary executable theme extensions.
- Automatic compiler or theme upgrades.
- Scheduled publication based on future timestamps.
- An Ideas feed in v1.
- Project detail pages, project documentation hosting, or automatic publication of every GitHub repository.
- User-authored iframe, script, form, or arbitrary embed support in Markdown.
- Rebuilding static output for Issue comments.
- Committing generated HTML back to a deployment branch.

## Further Notes

- The old `.html` URL decision is intentionally destructive and recorded as an accepted ADR. Cutover communication and observation of resulting 404 and indexing changes are operational responsibilities, not alias implementation work.
- GitHub Issue remains the only authoritative representation after upload. Internal IssueSnapshot and SiteModel values exist only for one compiler execution.
- The project working tree contains substantial pre-existing documentation and configuration work. Implementation must not stage, discard, reset, broadly format, commit, push, or overwrite unrelated changes.
- The Uploader Skill has already been authored and validated during design. Site Compiler, theme, workflow, and deployment source implementation has not begun.
- The next step after approval of this spec is `/to-tickets`, followed by fresh-context `/implement` work per ticket.
