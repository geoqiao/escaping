# SEO official requirements and evidence for geoqiao.me

Audit date: 2026-08-03 (Asia/Shanghai). This is a read-only public audit of
`https://geoqiao.me/`, its DNS, and the 68 URLs in its sitemap. Requirements
below come only from Chrome/Chromium, Google, web.dev, and GitHub documentation.
Site implications are observations or inferences, not statements by those
sources.

No authenticated GitHub Pages or Google Search Console (GSC) settings were
accessed. The mixed-content check inspected delivered HTML and the referenced
Theme CSS/JS; it is not a runtime Chrome trace of every dynamic request.

## 1. Valid TLS can coexist with Chrome security warnings

### Official facts

- A valid certificate secures the main HTTPS origin; it is not used when the
  main document is requested over HTTP, which Chrome treats as non-secure. An
  HTTPS page that interacts with HTTP subresources is mixed content and only
  partially protected. Chrome DevTools separates certificate problems from
  mixed-content problems and lists affected non-secure origins in **Security**.
  [Chrome DevTools](https://developer.chrome.com/docs/devtools/security)
- Current Chromium auto-upgrades HTTP image, audio, and video requests to HTTPS;
  if the upgraded resource fails, it is not loaded. Other blockable mixed
  content, including scripts, stylesheets, and iframes, is blocked by default.
  A browser/site policy can alter whether insecure content is allowed.
  [Chromium mixed-content autoupgrade](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/docs/security/autoupgrade-mixed.md)
- An HTTPS page whose form submits to an HTTP `action` has a mixed form. Chrome
  disables autofill, warns when the user fills it, and shows a full-page warning
  on submission. The valid certificate for the page does not protect the later
  HTTP form submission.
  [Chromium mixed-form policy](https://blog.chromium.org/2020/08/protecting-google-chrome-users-from.html)
- The literal address-bar treatment is version- and policy-dependent. Older
  Chrome guidance described a **Not Secure** chip for mixed images, while current
  Chromium normally upgrades or blocks them. Mixed forms and blocked resources
  can therefore produce warnings or broken behavior without necessarily using
  the same address-bar wording.
  [Chromium UI transition](https://blog.chromium.org/2019/10/no-more-mixed-messages-about-https.html)

### Implications for geoqiao.me

- `https://geoqiao.me/` returned `200` from `GitHub.com` with successful TLS
  validation. `http://geoqiao.me/` redirected to HTTPS, and
  `https://www.geoqiao.me/` redirected to the canonical apex HTTPS URL.
- All 68 sitemap pages, their delivered resource attributes, and the five
  referenced Theme CSS/JS files contained no `http://` resource request, HTTP
  form action, form, or inline CSS HTTP URL. This public static snapshot does
  not supply a mixed-content explanation for a current **Not Secure** report.
- If the warning is reproducible, capture the final URL and use the affected
  Chrome profile's **Security**, **Network**, **Issues**, and **Console** panels.
  That runtime evidence is needed to find a dynamically injected request,
  browser policy, stale response, or wording specific to that Chrome version.

## 2. GitHub Pages custom-domain HTTPS and DNS

### Official facts

- Correctly configured custom-domain Pages sites support HTTPS. Selecting
  **Enforce HTTPS** redirects every HTTP request to HTTPS; certificate
  provisioning begins only after GitHub's DNS check succeeds. HTTPS does not
  repair HTTP asset references inside the site.
  [GitHub Pages HTTPS](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https)
- An apex domain must use `ALIAS`/`ANAME` to the Pages default domain or the four
  GitHub Pages `A` records. GitHub also publishes optional `AAAA` records for
  IPv6. A `www` subdomain must be a `CNAME` directly to `<user>.github.io` or
  `<organization>.github.io`, without a repository name. Extra/conflicting
  records may prevent certificate issuance; wildcard DNS is discouraged because
  of takeover risk.
  [GitHub custom-domain DNS](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)
- If CAA records exist, at least one must allow `letsencrypt.org`. GitHub also
  recommends a persistent domain-verification TXT challenge to prevent another
  GitHub user from claiming the domain.
  [GitHub troubleshooting](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/troubleshooting-custom-domains-and-github-pages),
  [domain verification](https://docs.github.com/en/enterprise-cloud@latest/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages)

### Implications for geoqiao.me

- Public DNS returned all four required apex `A` records and
  `www.geoqiao.me CNAME geoqiao.github.io`. No apex `AAAA` was present; this is
  an optional IPv6 capability, not an IPv4/HTTPS failure. No CAA record was
  present, so CAA is not restricting Let's Encrypt.
- A random nonexistent subdomain returned NXDOMAIN, so this sample did not show
  wildcard behavior. The expected
  `_github-pages-challenge-geoqiao.geoqiao.me` TXT record was not present; GitHub
  domain verification should be confirmed in account settings.
- The observed redirects are consistent with **Enforce HTTPS**, but only
  authenticated **Settings → Pages** can confirm the checkbox and successful
  custom-domain check mark.

## 3. Search Console verification and sitemap submission

### Official facts

- A Domain property such as `geoqiao.me` covers all protocols and subdomains and
  requires DNS verification. A URL-prefix property such as
  `https://geoqiao.me/` covers only that exact prefix and supports several
  methods, including an HTML verification meta tag. Verification remains valid
  only while GSC can continue to find a valid token.
  [Property types](https://support.google.com/webmasters/answer/34592?hl=en),
  [ownership verification](https://support.google.com/webmasters/answer/9008080?hl=en)
- Submitting a sitemap means giving GSC its already-public URL; it is not a file
  upload. The Sitemaps report requires owner permission and reports fetch/parse
  status and errors. Only report/API submissions appear in that report, even if
  Google discovered the sitemap through `robots.txt`.
  [Sitemaps report](https://support.google.com/webmasters/answer/7451001?hl=en)
- Sitemap URLs should be absolute canonical URLs, and a root-level sitemap can
  cover the entire site. A successful submission is a discovery hint, not a
  crawl or indexing guarantee.
  [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)

### Implications for geoqiao.me

- The homepage contains a Google verification meta tag, which is compatible
  with URL-prefix verification. It does not prove the current property type,
  verified-owner status, or the existence of a Domain property; those remain
  authenticated GSC facts.
- [`robots.txt`](https://geoqiao.me/robots.txt) allows all crawlers and names
  [`sitemap.xml`](https://geoqiao.me/sitemap.xml). The root sitemap returned
  `200`, listed 68 absolute HTTPS URLs, and every listed URL returned `200` with
  the same self-referential canonical URL.
- GSC must still be checked for the exact property, sitemap submission URL,
  `Success`/error state, last read time, discovered URL count, and actual Page
  indexing results.

## 4. Google crawling, indexing, and search appearance

### Official facts

- The minimum technical eligibility requirements are: Googlebot is not blocked,
  the page returns HTTP `200`, and it has indexable content. Meeting them does
  not guarantee crawling, indexing, or serving. Search Essentials additionally
  covers spam policies and people-first, discoverable content.
  [Technical requirements](https://developers.google.com/search/docs/essentials/technical),
  [Search Essentials](https://developers.google.com/search/docs/essentials)
- `robots.txt` controls crawling, not reliable deindexing. A disallowed URL can
  still be indexed from external signals; use an accessible `noindex` rule when
  deindexing is intended.
  [Google robots.txt guidance](https://developers.google.com/search/docs/crawling-indexing/robots/intro)
- Redirects and `rel="canonical"` are strong canonical signals; sitemap inclusion
  is weaker. Google recommends a self-canonical, consistent internal links, and
  agreement among redirects, canonical annotations, and sitemap URLs.
  [Canonical guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- Every page should have a concise, descriptive, distinct `<title>`. Google
  primarily derives snippets from page content but may use an accurate,
  page-specific meta description; neither the title link nor snippet is
  guaranteed to reproduce the supplied text.
  [Title links](https://developers.google.com/search/docs/appearance/title-link),
  [snippets and descriptions](https://developers.google.com/search/docs/appearance/snippet)
- Structured data must describe visible page content, be accessible to
  Googlebot, and follow the feature-specific and general policies. Correct
  markup enables eligibility but does not guarantee a rich result.
  [Structured-data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
- Google's Article documentation currently has no required properties, but
  recommends applicable fields such as author, publication/modification dates,
  headline, and representative crawlable images. Breadcrumb eligibility requires
  a `BreadcrumbList` with at least two ordered `ListItem` entries representing a
  typical user path.
  [Article](https://developers.google.com/search/docs/appearance/structured-data/article),
  [Breadcrumb](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb)
- Google finds images in standard `<img src>` markup, not CSS background images.
  Images should be near relevant text, fast and high quality, with useful,
  information-rich alt text in the page's context and descriptive filenames.
  [Google image SEO](https://developers.google.com/search/docs/appearance/google-images)
- Good Core Web Vitals targets are LCP at or below 2.5 seconds, INP below 200 ms,
  and CLS below 0.1. GSC evaluates URL groups separately for mobile and desktop
  from real-user data at the 75th percentile over the previous 28 days.
  [Search and Core Web Vitals](https://developers.google.com/search/docs/appearance/core-web-vitals),
  [GSC Core Web Vitals report](https://support.google.com/webmasters/answer/9205520?hl=en)

### Implications for geoqiao.me

- The 68 sitemap URLs returned `200`, were allowed by `robots.txt`, and had no
  response-header or HTML `noindex`. These are positive eligibility signals, not
  proof that Google has crawled or indexed them.
- Canonical alignment passed for all 68 URLs, including the HTTP and `www`
  redirects to the apex HTTPS origin.
- All pages had a `<title>`, but the four Blog archive pages share
  `Blog - geoqiao's Blog`. Thirty-three pages have an empty meta description,
  and three pages reuse the description `背景`. These are search-presentation
  quality gaps, not indexing blockers.
- Thirty-four article pages contain parseable `BlogPosting` JSON-LD with author,
  dates, description, headline, and URL. None supplies the recommended `image`
  property, and no page supplies `BreadcrumbList`. These are optional rich-result
  enhancement gaps, not evidence of invalid pages.
- All eight `<img>` elements have an `alt` attribute, but all six content images
  use only `Image` or `image`; their text should describe the actual image in its
  article context. Article-image eligibility also needs suitable crawlable,
  representative images.
- No authenticated GSC or CrUX field data was available, so current indexing,
  rich-result status, and Core Web Vitals remain unknown.

## 5. Required GSC 7/28/90-day baseline

### Official data constraints

The Performance report provides clicks, impressions, CTR, and average position,
grouped or filtered by date, query, page, country, device, and search appearance.
Most page data is credited to Google's selected canonical. Except for the
24-hour view, dates use Pacific Time; use complete days because recent data can
be preliminary. UI table exports are limited to the rows shown.
[Performance dimensions](https://support.google.com/webmasters/answer/17011259?hl=en),
[data counting and freshness](https://support.google.com/webmasters/answer/17011364?hl=en),
[export limits](https://support.google.com/webmasters/answer/12919797?hl=en)

### Baseline package

Use one verified property, `search type = Web`, no hidden filters, and the same
latest complete Pacific-Time end date for all three rolling windows. Record the
property identifier/type, export timestamp, exact dates, search type, and every
filter with each export.

| Dataset | Required fields / cuts | Window handling |
| --- | --- | --- |
| Performance totals | Clicks, impressions, CTR, average position | 7, 28, and 90 complete days; also export the immediately preceding equal-length comparison |
| Daily trend | Date plus all four metrics | One daily series covering at least 90 days; derive the three windows from the same frozen export |
| Query and page tables | Query/page plus all four metrics | Export each table for 7/28/90; retain zero-click/high-impression rows and note privacy/truncation limits |
| Audience and result cuts | Country, device, and search appearance plus all four metrics | Export each cut for 7/28/90 with identical filters |
| Page indexing | Indexed count, not-indexed count, every reason and affected count; sitemap-filtered view | Snapshot on the audit date; preserve future snapshots to reconstruct change over time |
| Sitemaps | Submitted URL, status, last read, discovered pages, errors | Snapshot on the audit date; `robots.txt` discovery alone does not prove report submission |
| URL Inspection sample | Homepage, Blog index, newest and representative old posts: fetch/index state, last crawl, user and Google canonical | Snapshot on the audit date and after material fixes |
| Core Web Vitals | Mobile/desktop Good, Needs improvement, Poor URL counts; issue groups and p75 LCP/INP/CLS | GSC's native window is 28 days; do not relabel it as 7- or 90-day data. Build history from dated snapshots |
| Rich results and policy | Article/Breadcrumb valid/invalid items if reports exist; Manual Actions and Security Issues state | Snapshot on the audit date; performance impact is measured through the Search appearance cut |

The Page indexing report supplies indexed/not-indexed counts and reasons, while
the Core Web Vitals report is a 28-day field-data view rather than an arbitrary
date-range report.
[Page indexing report](https://support.google.com/webmasters/answer/7440203?hl=en),
[Core Web Vitals report](https://support.google.com/webmasters/answer/9205520?hl=en)
