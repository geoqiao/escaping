/*
 * PROTOTYPE — throwaway UI only.
 * Three variants of geoqiao.me, switchable via ?variant=, on one static route.
 */

const SITE = {
  author: "geoqiao",
  title: "geoqiao's Blog",
  role: "贷后策略分析师 / tool tinkerer",
  bio: "一名金融行业的贷后策略分析师，喜欢折腾工具，也享受用代码解决重复性工作。工作之余，我喜欢记录生活中的碎片。",
  avatar: "https://github.com/geoqiao.png",
  links: [
    ["GitHub", "https://github.com/geoqiao"],
    ["Twitter/X", "https://twitter.com/geoqiao"],
  ],
};

const POSTS = [
  {
    issue: 41,
    date: "2026-08-01",
    title: "What's on My Pi Agent?：把 90% 的 Codex Desktop 装进终端",
    description: "Codex Desktop 很顺手，只是我的 MacBook M1 Pro 跑不起它，所以我用 Pi、Herdr 和 Neovim 搭了一套终端工作台。",
    tags: ["ai-agent", "pi", "herdr", "terminal-workflow"],
  },
  {
    issue: 36,
    date: "2026-04-18",
    title: "从 Obsidian 到博客：我如何用一条命令把笔记变成网站",
    description: "把本地写作、GitHub Issues 和静态站点串成一条足够简单的发布路径。",
    tags: ["obsidian", "escaping", "workflow"],
  },
  {
    issue: 35,
    date: "2026-04-18",
    title: "从 Superpowers 学习高质量 AI 协作：一份给策略分析师的 Claude Code 指南",
    description: "从策略分析工作的真实约束出发，整理一套可复用的 AI 协作方法。",
    tags: ["ai-workflow", "data-analysis", "claude-code"],
  },
  {
    issue: 34,
    date: "2026-04-05",
    title: "不懂 Git、不会前端，一个文科生的 GitHub Blog",
    description: "一个从需求、踩坑到上线的个人博客实践记录。",
    tags: ["escaping", "python"],
  },
  {
    issue: 32,
    date: "2026-03-21",
    title: "Vibe Coding 实战后感 — github_blog with Trae",
    description: "当自然语言成为主要输入方式，开发流程里哪些部分真的变快了？",
    tags: ["python", "vibe-coding", "vscode"],
  },
  {
    issue: 31,
    date: "2026-02-21",
    title: "2025 年终总结：关注自己",
    description: "把注意力收回来，记录这一年真正留下来的东西。",
    tags: ["summary"],
  },
  {
    issue: 30,
    date: "2025-02-05",
    title: "我喜欢冬天的下午走路去成都的茶馆喝茶",
    description: "一段关于冬天、散步、成都和茶馆的生活碎片。",
    tags: ["travel"],
  },
];

const TAGS = [
  ["python", 15],
  ["vscode", 4],
  ["data-analysis", 3],
  ["escaping", 2],
  ["claude-code", 2],
  ["obsidian", 2],
  ["summary", 2],
  ["macos", 2],
  ["ai-agent", 1],
  ["herdr", 1],
  ["pi", 1],
  ["terminal-workflow", 1],
  ["travel", 1],
  ["vim", 1],
  ["sql", 1],
  ["excel", 1],
];

const NAV = [
  ["Home", "home"],
  ["Blog", "blog"],
  ["Ideas", "ideas"],
  ["Projects", "projects"],
  ["Tags", "tags"],
  ["About", "about"],
];

const VARIANTS = [
  { key: "A", slug: "ledger", name: "Signal Ledger / 策略台账" },
  { key: "A2", slug: "quiet-ledger", name: "Quiet Ledger / 安静台账" },
  { key: "B", slug: "workbench", name: "Workbench / 工具工作台" },
  { key: "C", slug: "archive", name: "Issue Archive / 议题档案" },
];

function isLedgerVariant(variant) {
  return variant === "ledger" || variant === "quiet-ledger";
}

const PAGE_TITLES = {
  home: "Home",
  blog: "Blog",
  post: "Post #41",
  ideas: "Ideas",
  projects: "Projects",
  tags: "Tags",
  about: "About",
};

const app = document.querySelector("#app");
const previousButton = document.querySelector("#variant-prev");
const nextButton = document.querySelector("#variant-next");
const variantKey = document.querySelector("#variant-key");
const variantName = document.querySelector("#variant-name");

function currentState() {
  const params = new URLSearchParams(window.location.search);
  const variant = VARIANTS.find((item) => item.slug === params.get("variant")) || VARIANTS[0];
  const requestedPage = params.get("page") || "home";
  const page = Object.hasOwn(PAGE_TITLES, requestedPage) ? requestedPage : "home";
  const requestedMode = params.get("mode");
  const rememberedMode = window.sessionStorage.getItem("ledger-mode");
  const mode = (requestedMode || rememberedMode) === "dark" ? "dark" : "light";
  if (requestedMode === "dark" || requestedMode === "light") window.sessionStorage.setItem("ledger-mode", requestedMode);
  return { variant, page, mode };
}

function hrefFor(variant, page, mode = currentState().mode) {
  const modeQuery = isLedgerVariant(variant) ? `&mode=${encodeURIComponent(mode)}` : "";
  return `?variant=${encodeURIComponent(variant)}&page=${encodeURIComponent(page)}${modeQuery}`;
}

function pageLink(variant, page, label, className = "") {
  return `<a href="${hrefFor(variant, page)}" data-page="${page}" class="${className}">${label}</a>`;
}

function tagLinks(variant, tags, className = "tag") {
  return tags.map((tag) => pageLink(variant, "tags", tag, className)).join("");
}

function avatarMarkup(className = "") {
  return `<img class="${className}" src="${SITE.avatar}" alt="${SITE.author} 的头像" width="160" height="160">`;
}

function externalLinks(className = "") {
  return SITE.links
    .map(([label, url]) => `<a class="${className}" href="${url}" target="_blank" rel="noreferrer">${label}<span class="sr-only">（新窗口）</span></a>`)
    .join("");
}

function navMarkup(variant, page, className, itemClassName = "") {
  const items = NAV.map(([label, target]) => {
    const active = page === target || (page === "post" && target === "blog");
    return `<li>${pageLink(variant, target, label, `${itemClassName}${active ? " is-active" : ""}`)}${active ? '<span class="sr-only">（当前页面）</span>' : ""}</li>`;
  }).join("");
  return `<nav class="${className}" aria-label="主要导航"><ul>${items}<li><a class="${itemClassName}" href="https://geoqiao.me/atom.xml">RSS</a></li></ul></nav>`;
}

function articleBody(variant, prefix) {
  return `
    <p class="${prefix}-lede">Codex Desktop 很顺手，只是我的 MacBook M1 Pro 跑不起它。四年没有转过的风扇，只要打开 Codex 就转不停。</p>
    <p>所以我使用 <strong>Pi + Herdr + Neovim</strong>，打造了一个终端中的 Codex Desktop。它们不是在模仿同一个产品，而是各自负责自己最擅长的部分。</p>
    <figure class="${prefix}-workflow" aria-labelledby="workflow-caption-${prefix}">
      <div class="workflow-node"><span>01</span><strong>Herdr</strong><small>workspace / pane</small></div>
      <span class="workflow-arrow" aria-hidden="true">→</span>
      <div class="workflow-node"><span>02</span><strong>Pi</strong><small>agent runtime</small></div>
      <span class="workflow-arrow" aria-hidden="true">→</span>
      <div class="workflow-node"><span>03</span><strong>Neovim</strong><small>code / buffer</small></div>
      <figcaption id="workflow-caption-${prefix}">把工作台、Agent 与代码编辑拆给不同工具。</figcaption>
    </figure>
    <ul>
      <li><strong>Herdr</strong> 管工作台：workspace、tab、pane、布局、多 Agent 侧边栏。</li>
      <li><strong>Pi</strong> 管 Agent：模型循环、工具调用、会话、扩展。</li>
      <li><strong>Neovim</strong> 管代码：浏览、编辑、Buffer，并通过 <code>pi-nvim</code> 把上下文喂给 Pi。</li>
    </ul>
    <h2 id="trace">Trace</h2>
    <p>右侧 pane 固定放 Neovim，查看、编辑和跳转文件都不用离开终端。需要让 Pi 看代码时，可以把当前文件、选区或整个 Buffer 直接送到左侧会话。</p>
    <pre><code><span class="code-comment"># 恢复日常工作区</span>
herdr workspace open geoqiao
herdr tab restore code --layout 50:50
pi --session current</code></pre>
    <h2 id="parts">软件与插件</h2>
    <div class="table-scroll" tabindex="0" aria-label="软件与插件表格，可横向滚动">
      <table>
        <thead><tr><th>名称</th><th>用途</th><th>入口</th></tr></thead>
        <tbody>
          <tr><td>Pi</td><td>Agent runtime</td><td><a href="https://github.com/earendil-works/pi">GitHub</a></td></tr>
          <tr><td>Herdr</td><td>Workspace 与多 Agent TUI</td><td><a href="https://github.com/ogulcancelik/herdr">GitHub</a></td></tr>
          <tr><td>Neovim</td><td>编辑器</td><td><a href="https://neovim.io/">官网</a></td></tr>
        </tbody>
      </table>
    </div>
    <h2 id="tradeoffs">PROS &amp; CONS</h2>
    <blockquote>这并不适合想要开箱即用的人。AI 可以解决大部分配置问题，但日常操作仍然需要适应。</blockquote>
    <p>优点很直接：风扇不转了，token 更耐用了，工作流也真正变成了自己可以理解和修改的东西。</p>
    <p class="article-back">${pageLink(variant, "blog", "← 返回 Blog")}</p>
  `;
}

function commentsPlaceholder(issue, variantClass) {
  return `
    <section class="comments-placeholder ${variantClass}" aria-labelledby="comments-title">
      <div>
        <p class="comments-kicker">COMMENTS / GITHUB ISSUE #${issue}</p>
        <h2 id="comments-title">继续讨论</h2>
        <p>生产站中 Utterances 会出现在这里，并继续跟随站点主题。</p>
      </div>
      <a href="https://github.com/geoqiao/geoqiao.github.io/issues/${issue}">在 GitHub 查看讨论 ↗</a>
    </section>
  `;
}

function emptyIdeas(variant, prefix) {
  return `
    <section class="${prefix}-empty">
      <span aria-hidden="true">∅</span>
      <p class="eyebrow">IDEAS / EMPTY STATE</p>
      <h1>这里还没有发布的 Idea。</h1>
      <p>短想法会留在这里；完整文章仍然进入 Blog。这个 demo 刻意保留当前真实空状态。</p>
      ${pageLink(variant, "blog", "先去看 Blog", `${prefix}-button`)}
    </section>
  `;
}

function ledgerNavigation(variant, page) {
  return navMarkup(variant, page, "ledger-nav", "ledger-nav-link");
}

function ledgerAside(variant, page, quiet = false) {
  if (quiet) {
    if (page !== "home") return "";
    return `
      <aside class="ledger-aside ledger-quiet-aside">
        <div class="ledger-avatar-wrap">${avatarMarkup("ledger-avatar")}</div>
        <p class="ledger-label">PROFILE / ACTIVE</p>
        <h2>${SITE.author}</h2>
        <p class="ledger-role">${SITE.role}</p>
        <p class="ledger-bio">${SITE.bio}</p>
        <div class="ledger-socials">${externalLinks()}</div>
        <div class="ledger-project-note">
          <span>FEATURED PROJECT</span>
          <a href="https://github.com/geoqiao/escaping">escaping ↗</a>
          <small>Python · static publishing</small>
        </div>
      </aside>
    `;
  }
  if (page === "post") {
    return `
      <aside class="ledger-aside ledger-post-aside">
        <p class="ledger-label">ENTRY / #41</p>
        <dl class="ledger-facts">
          <div><dt>Created</dt><dd>2026-08-01</dd></div>
          <div><dt>Reading</dt><dd>8 min</dd></div>
          <div><dt>State</dt><dd><span class="signal-dot is-live"></span> published</dd></div>
        </dl>
        <nav aria-label="文章目录" class="ledger-toc">
          <p>On this page</p>
          <a href="#trace">Trace</a>
          <a href="#parts">软件与插件</a>
          <a href="#tradeoffs">Pros &amp; Cons</a>
        </nav>
      </aside>
    `;
  }
  return `
    <aside class="ledger-aside">
      <div class="ledger-avatar-wrap">${avatarMarkup("ledger-avatar")}</div>
      <p class="ledger-label">PROFILE / ACTIVE</p>
      <h2>${SITE.author}</h2>
      <p class="ledger-role">${SITE.role}</p>
      <p class="ledger-bio">${SITE.bio}</p>
      <div class="ledger-socials">${externalLinks()}</div>
      <div class="ledger-project-note">
        <span>FEATURED PROJECT</span>
        <a href="https://github.com/geoqiao/escaping">escaping ↗</a>
        <small>Python · static publishing</small>
      </div>
    </aside>
  `;
}

function ledgerPostRows(variant, posts = POSTS.slice(0, 5), quiet = false) {
  if (quiet) {
    return posts.map((post, index) => `
      <article class="ledger-row ledger-row-quiet">
        <time datetime="${post.date}">${post.date.replaceAll("-", ".")}</time>
        <div class="ledger-track" aria-hidden="true"><span class="${index === 0 ? "is-live" : ""}"></span></div>
        <div class="ledger-entry">
          <div class="ledger-entry-top"><span>ISSUE #${post.issue}</span></div>
          <h3>${pageLink(variant, "post", post.title)}</h3>
          <div class="ledger-tags">${tagLinks(variant, post.tags)}</div>
        </div>
      </article>
    `).join("");
  }
  return posts.map((post, index) => `
    <article class="ledger-row">
      <time datetime="${post.date}">${post.date.replaceAll("-", ".")}</time>
      <div class="ledger-track" aria-hidden="true"><span class="${index === 0 ? "is-live" : ""}"></span></div>
      <div class="ledger-entry">
        <div class="ledger-entry-top"><span>ISSUE #${post.issue}</span><span>${String(index + 1).padStart(2, "0")}</span></div>
        <h3>${pageLink(variant, "post", post.title)}</h3>
        <p>${post.description}</p>
        <div class="ledger-tags">${tagLinks(variant, post.tags)}</div>
      </div>
    </article>
  `).join("");
}

function ledgerPage(variant, page, quiet = false) {
  if (quiet) {
    if (page === "home") {
      return `
        <section class="ledger-hero ledger-quiet-hero">
          <h1><span>演悲欢离合,当代岂无前代事?</span><span>观抑扬褒贬,座中常有剧中人。</span></h1>
        </section>
        <section class="ledger-section ledger-quiet-section" aria-labelledby="ledger-latest">
          <header class="ledger-section-head">
            <h2 id="ledger-latest">Recent Posts</h2>
            ${pageLink(variant, "blog", "完整归档 →")}
          </header>
          <div class="ledger-list">${ledgerPostRows(variant, POSTS.slice(0, 5), true)}</div>
        </section>
      `;
    }
    if (page === "blog") {
      return `
        <section class="ledger-page-head ledger-quiet-page-head">
          <h1>Blog</h1>
          <p>关于 Python、数据分析、AI workflow，以及偶尔出现的生活碎片。</p>
        </section>
        <div class="ledger-list ledger-list-archive">${ledgerPostRows(variant, POSTS, true)}</div>
      `;
    }
    if (page === "post") {
      const post = POSTS[0];
      return `
        <article class="ledger-article ledger-quiet-article">
          <header class="ledger-article-head">
            <p class="eyebrow">BLOG / ISSUE #${post.issue}</p>
            <h1>${post.title}</h1>
            <div class="ledger-quiet-article-meta">
              <time datetime="${post.date}">${post.date.replaceAll("-", ".")}</time>
              <span>8 min read</span>
              <div class="ledger-article-tags">${tagLinks(variant, post.tags)}</div>
            </div>
          </header>
          <div class="ledger-prose">${articleBody(variant, "ledger")}</div>
        </article>
        ${commentsPlaceholder(post.issue, "ledger-comments")}
      `;
    }
    if (page === "ideas") {
      return `
        <section class="ledger-empty ledger-quiet-empty">
          <h1>这里还没有发布的 Idea。</h1>
          <p>短想法会留在这里；完整文章仍然进入 Blog。</p>
          ${pageLink(variant, "blog", "先去看 Blog", "ledger-button")}
        </section>
      `;
    }
    if (page === "projects") {
      return `
        <section class="ledger-page-head ledger-quiet-page-head"><h1>Projects</h1><p>只记录仍愿意继续维护的东西。</p></section>
        <article class="ledger-project ledger-quiet-project">
          <div>
            <h2><a href="https://github.com/geoqiao/escaping">escaping ↗</a></h2>
            <p>A minimalist and highly automated personal blog framework. 使用 GitHub Issues 写作，由 Python 编译为静态站点。</p>
            <p class="ledger-quiet-project-meta">Python · Open Source · Updated 2026</p>
          </div>
        </article>
      `;
    }
    if (page === "tags") {
      return `
        <section class="ledger-page-head ledger-quiet-page-head"><h1>Tags</h1><p>按主题浏览公开记录。</p></section>
        <div class="ledger-quiet-tag-list">
          ${TAGS.map(([tag, count]) => `<a href="${hrefFor(variant, "blog")}" data-page="blog"><strong>#${tag}</strong><span>${count}</span></a>`).join("")}
        </div>
      `;
    }
    return `
      <article class="ledger-about ledger-quiet-about">
        <header><h1>关于我</h1></header>
        <div class="ledger-about-grid">
          <div>${avatarMarkup("ledger-about-avatar")}<p class="ledger-caption">geoqiao / Chengdu</p></div>
          <div class="ledger-prose"><p class="ledger-lede">你好，我是 geoqiao。</p><p>我是一名金融行业的贷后策略分析师，喜欢折腾工具，也享受用代码解决重复性工作。</p><p>工作之余，我喜欢记录生活中的碎片。</p><p class="ledger-inline-links">${externalLinks()}</p></div>
        </div>
      </article>
      ${commentsPlaceholder(42, "ledger-comments")}
    `;
  }
  if (page === "home") {
    return `
      <section class="ledger-hero">
        <div>
          <p class="eyebrow">PERSONAL SIGNAL LOG / CHENGDU</p>
          <h1><span>把策略、工具与生活，</span><span>记成一份可回看的<span class="ledger-title-tail">台账。</span></span></h1>
        </div>
        <div class="ledger-hero-note">
          <span class="signal-dot is-live"></span>
          <p><strong>Current signal</strong>正在折腾更轻、更耐用的 AI coding workflow。</p>
        </div>
      </section>
      <section class="ledger-section" aria-labelledby="ledger-latest">
        <header class="ledger-section-head">
          <div><p class="eyebrow">LATEST / 05 ENTRIES</p><h2 id="ledger-latest">Recent Posts</h2></div>
          ${pageLink(variant, "blog", "完整归档 →")}
        </header>
        <div class="ledger-list">${ledgerPostRows(variant)}</div>
      </section>
    `;
  }
  if (page === "blog") {
    return `
      <section class="ledger-page-head">
        <p class="eyebrow">ARCHIVE / 33 PUBLISHED</p>
        <h1>Blog</h1>
        <p>关于 Python、数据分析、AI workflow，以及偶尔出现的生活碎片。</p>
      </section>
      <div class="ledger-filter" aria-label="文章筛选预览"><span class="is-selected">ALL 33</span><span>TOOLS 19</span><span>LIFE 07</span><span>ANALYSIS 07</span></div>
      <div class="ledger-list ledger-list-archive">${ledgerPostRows(variant, POSTS)}</div>
    `;
  }
  if (page === "post") {
    const post = POSTS[0];
    return `
      <article class="ledger-article">
        <header class="ledger-article-head">
          <p class="eyebrow">BLOG / ISSUE #${post.issue}</p>
          <h1>${post.title}</h1>
          <p>${post.description}</p>
          <div class="ledger-article-tags">${tagLinks(variant, post.tags)}</div>
        </header>
        <div class="ledger-prose">${articleBody(variant, "ledger")}</div>
      </article>
      ${commentsPlaceholder(post.issue, "ledger-comments")}
    `;
  }
  if (page === "ideas") return emptyIdeas(variant, "ledger");
  if (page === "projects") {
    return `
      <section class="ledger-page-head"><p class="eyebrow">PROJECT CATALOG / 01</p><h1>Projects</h1><p>少而明确：只记录仍愿意继续维护的东西。</p></section>
      <article class="ledger-project">
        <div class="ledger-project-index">01</div>
        <div><p class="eyebrow">PYTHON / OPEN SOURCE</p><h2><a href="https://github.com/geoqiao/escaping">escaping ↗</a></h2><p>A minimalist and highly automated personal blog framework. 使用 GitHub Issues 写作，由 Python 编译为静态站点。</p><div class="ledger-project-stats"><span>★ 1</span><span>⑂ 2</span><span>updated 2026</span></div></div>
      </article>
    `;
  }
  if (page === "tags") {
    return `
      <section class="ledger-page-head"><p class="eyebrow">TAXONOMY / ${TAGS.length} SHOWN</p><h1>Tags</h1><p>标签不是装饰，而是一份内容暴露度报告。</p></section>
      <div class="ledger-tag-report">
        ${TAGS.map(([tag, count], index) => `<a href="${hrefFor(variant, "blog")}" data-page="blog"><span>${String(index + 1).padStart(2, "0")}</span><strong>${tag}</strong><i style="--count:${count}"></i><em>${count}</em></a>`).join("")}
      </div>
    `;
  }
  return `
    <article class="ledger-about">
      <header><p class="eyebrow">PROFILE / UPDATED 2026.08</p><h1>关于我</h1></header>
      <div class="ledger-about-grid">
        <div>${avatarMarkup("ledger-about-avatar")}<p class="ledger-caption">geoqiao / Chengdu</p></div>
        <div class="ledger-prose"><p class="ledger-lede">你好，我是 geoqiao。</p><p>我是一名金融行业的贷后策略分析师，喜欢折腾工具，也享受用代码解决重复性工作。</p><p>工作之余，我喜欢记录生活中的碎片。</p><h2>Links</h2><p class="ledger-inline-links">${externalLinks()}</p></div>
      </div>
    </article>
    ${commentsPlaceholder(42, "ledger-comments")}
  `;
}

function renderLedger(page, mode, variant = "ledger") {
  const isDark = mode === "dark";
  const quiet = variant === "quiet-ledger";
  const aside = ledgerAside(variant, page, quiet);
  const main = `<main class="ledger-main" id="prototype-main" tabindex="-1">${ledgerPage(variant, page, quiet)}</main>`;
  return `
    <div class="direction direction-ledger${quiet ? " is-quiet" : ""} ${page === "home" ? "is-home" : "is-inner"}">
      <header class="ledger-header">
        ${pageLink(variant, "home", `<strong>${SITE.author}</strong><span>${quiet ? "/ notes" : "/ signal ledger"}</span>`, "ledger-brand")}
        <div class="ledger-header-actions">
          ${ledgerNavigation(variant, page)}
          <button class="ledger-mode-toggle" type="button" data-ledger-mode aria-pressed="${isDark}" aria-label="切换到${isDark ? "浅色" : "深色"}模式">
            <span aria-hidden="true">◐</span><span>${isDark ? "Light" : "Dark"}</span>
          </button>
        </div>
      </header>
      <div class="ledger-shell">
        ${quiet ? `${main}${aside}` : `${aside}${main}`}
      </div>
      <footer class="ledger-footer">${quiet ? `<span>© geoqiao</span><a href="https://geoqiao.me/atom.xml">RSS</a><a href="https://github.com/geoqiao/escaping">source ↗</a>` : `<span>© geoqiao</span><span>Generated from GitHub Issues</span><a href="https://github.com/geoqiao/escaping">source ↗</a>`}</footer>
    </div>
  `;
}

function workbenchNavigation(variant, page) {
  const icons = { home: "⌂", blog: "≡", ideas: "✦", projects: "◇", tags: "#", about: "@" };
  return `<nav class="wb-nav" aria-label="Workspace navigation"><p>WORKSPACE</p><ul>${NAV.map(([label, target]) => {
    const active = page === target || (page === "post" && target === "blog");
    return `<li>${pageLink(variant, target, `<span aria-hidden="true">${icons[target]}</span><span>${label}</span>`, active ? "is-active" : "")}</li>`;
  }).join("")}</ul></nav>`;
}

function wbPosts(variant, posts = POSTS.slice(0, 5)) {
  return `<ol class="wb-post-list">${posts.map((post) => `
    <li>
      <span class="wb-file-icon" aria-hidden="true">md</span>
      <div><h3>${pageLink(variant, "post", post.title)}</h3><p>${post.description}</p><div>${tagLinks(variant, post.tags)}</div></div>
      <time datetime="${post.date}">${post.date.slice(5)}</time>
    </li>
  `).join("")}</ol>`;
}

function wbContext(variant, page) {
  if (page === "post") {
    return `
      <aside class="wb-context">
        <section class="wb-panel"><header>outline.json</header><nav class="wb-outline" aria-label="文章目录"><a href="#trace"><span>02</span> Trace</a><a href="#parts"><span>03</span> 软件与插件</a><a href="#tradeoffs"><span>04</span> Pros &amp; Cons</a></nav></section>
        <section class="wb-panel wb-metadata"><header>metadata</header><dl><div><dt>issue</dt><dd>#41</dd></div><div><dt>created</dt><dd>2026-08-01</dd></div><div><dt>comments</dt><dd>enabled</dd></div></dl></section>
      </aside>
    `;
  }
  return `
    <aside class="wb-context">
      <section class="wb-panel wb-profile-panel">
        <header>profile.json</header>
        ${avatarMarkup("wb-avatar")}
        <pre>{
  "name": "geoqiao",
  "role": "strategy analyst",
  "location": "Chengdu",
  "status": "tinkering"
}</pre>
        <div class="wb-socials">${externalLinks()}</div>
      </section>
      <section class="wb-panel wb-now">
        <header>now.log</header>
        <p><span class="wb-live"></span> building</p>
        <strong>escaping</strong>
        <small>Issue CMS → static site</small>
        <a href="https://github.com/geoqiao/escaping">open repository ↗</a>
      </section>
    </aside>
  `;
}

function wbPage(variant, page) {
  if (page === "home") {
    return `
      <div class="wb-home-main">
        <section class="wb-pane wb-readme">
          <header><span>README.md</span><span>●</span></header>
          <div class="wb-pane-body">
            <p class="wb-comment">// strategy, tools, and fragments</p>
            <h1>你好，我是 <span>geoqiao</span>。</h1>
            <p class="wb-intro">${SITE.bio}</p>
            <div class="wb-trace" aria-label="当前终端工作流：Herdr 连接 Pi 与 Neovim">
              <div><small>workspace</small><strong>Herdr</strong></div><span>connects</span><div><small>agent</small><strong>Pi</strong></div><span>reads</span><div><small>editor</small><strong>Neovim</strong></div>
            </div>
          </div>
        </section>
        <section class="wb-pane wb-recent">
          <header><span>recent-posts/</span>${pageLink(variant, "blog", "open all ↗")}</header>
          ${wbPosts(variant)}
        </section>
      </div>
      ${wbContext(variant, page)}
    `;
  }
  if (page === "blog") {
    return `
      <section class="wb-pane wb-browser">
        <header><span>~/content/blog</span><span>33 files · sorted by created ↓</span></header>
        <div class="wb-page-title"><p class="wb-comment">// published writing</p><h1>Blog</h1><p>工具、数据分析、AI 协作，以及一些生活日志。</p></div>
        ${wbPosts(variant, POSTS)}
      </section>
      <aside class="wb-context"><section class="wb-panel"><header>quick-filter</header><div class="wb-filter"><button class="is-active">all <span>33</span></button><button>python <span>15</span></button><button>tools <span>12</span></button><button>life <span>06</span></button></div></section><section class="wb-panel wb-shortcut"><header>keyboard</header><p><kbd>j</kbd><kbd>k</kbd> browse posts</p><p><kbd>↵</kbd> open selected</p></section></aside>
    `;
  }
  if (page === "post") {
    const post = POSTS[0];
    return `
      <article class="wb-pane wb-article">
        <header><span>blog/${post.issue}-pi-agent.md</span><span>UTF-8 · Markdown</span></header>
        <div class="wb-article-body">
          <div class="wb-line-number" aria-hidden="true">01<br>02<br>03<br>04<br>05<br>06<br>07<br>08<br>09<br>10<br>11<br>12<br>13<br>14<br>15<br>16<br>17<br>18</div>
          <div class="wb-prose"><p class="wb-comment">---<br>issue: ${post.issue}<br>created: ${post.date}<br>---</p><h1>${post.title}</h1><div class="wb-article-tags">${tagLinks(variant, post.tags)}</div>${articleBody(variant, "wb")}</div>
        </div>
        ${commentsPlaceholder(post.issue, "wb-comments")}
      </article>
      ${wbContext(variant, page)}
    `;
  }
  if (page === "ideas") return `<section class="wb-pane wb-empty-pane"><header><span>~/content/ideas</span><span>0 files</span></header>${emptyIdeas(variant, "wb")}</section>${wbContext(variant, page)}`;
  if (page === "projects") {
    return `
      <section class="wb-pane wb-projects">
        <header><span>~/projects</span><span>1 repository</span></header>
        <div class="wb-page-title"><p class="wb-comment">// things I maintain</p><h1>Projects</h1></div>
        <article class="wb-project-tree"><div class="wb-tree"><span>▾ escaping/</span><span>├─ src/github_blog/</span><span>├─ templates/</span><span>├─ tests/</span><span>└─ README.md</span></div><div class="wb-project-readme"><p class="wb-comment">README.md</p><h2>escaping</h2><p>A minimalist and highly automated personal blog framework.</p><dl><div><dt>language</dt><dd>Python</dd></div><div><dt>stars</dt><dd>1</dd></div><div><dt>forks</dt><dd>2</dd></div></dl><a href="https://github.com/geoqiao/escaping">github.com/geoqiao/escaping ↗</a></div></article>
      </section>
      ${wbContext(variant, page)}
    `;
  }
  if (page === "tags") {
    return `
      <section class="wb-pane wb-tags-page">
        <header><span>tags.map</span><span>${TAGS.length} symbols</span></header>
        <div class="wb-page-title"><p class="wb-comment">// content index</p><h1>Tags</h1></div>
        <div class="wb-tag-map">${TAGS.map(([tag, count], index) => `<a href="${hrefFor(variant, "blog")}" data-page="blog"><span class="wb-tag-key">${String(index).padStart(2, "0")}</span><strong>${tag}</strong><span class="wb-tag-dots"></span><em>${count}</em></a>`).join("")}</div>
      </section>
      ${wbContext(variant, page)}
    `;
  }
  return `
    <article class="wb-pane wb-about">
      <header><span>~/about/profile.md</span><span>saved</span></header>
      <div class="wb-about-body"><div>${avatarMarkup("wb-about-avatar")}<div class="wb-about-links">${externalLinks()}</div></div><div class="wb-prose"><p class="wb-comment"># about</p><h1>关于我</h1><p class="wb-lede">你好，我是 geoqiao。</p><p>我是一名金融行业的贷后策略分析师，喜欢折腾工具，也享受用代码解决重复性工作。</p><p>工作之余，我喜欢记录生活中的碎片。</p><pre><code>interests = ["Python", "AI agents", "writing", "walking"]</code></pre></div></div>
      ${commentsPlaceholder(42, "wb-comments")}
    </article>
    ${wbContext(variant, page)}
  `;
}

function renderWorkbench(page) {
  const variant = "workbench";
  return `
    <div class="direction direction-workbench">
      <div class="wb-frame">
        <aside class="wb-rail">
          ${pageLink(variant, "home", `<span>gq<span class="wb-cursor">_</span></span><small>personal.workspace</small>`, "wb-brand")}
          ${workbenchNavigation(variant, page)}
          <div class="wb-rail-foot"><span><i class="wb-live"></i> online</span>${externalLinks()}</div>
        </aside>
        <section class="wb-workspace">
          <header class="wb-toolbar">
            <div class="wb-window-dots" aria-hidden="true"><i></i><i></i><i></i></div>
            <p><span>geoqiao.me</span> / ${PAGE_TITLES[page].toLowerCase().replaceAll(" ", "-")}</p>
            <div class="wb-build"><span></span> site:ready</div>
          </header>
          <main class="wb-stage" id="prototype-main" tabindex="-1">${wbPage(variant, page)}</main>
          <footer class="wb-status"><span>main*</span><span>UTF-8</span><span>zh-CN</span><span>Issues CMS</span></footer>
        </section>
      </div>
    </div>
  `;
}

function archiveNavigation(variant, page) {
  return navMarkup(variant, page, "archive-nav", "archive-nav-link");
}

function archiveRows(variant, posts = POSTS.slice(0, 5)) {
  return posts.map((post) => `
    <article class="archive-row">
      <div class="archive-issue"><span>#</span>${post.issue}</div>
      <time datetime="${post.date}">${post.date}</time>
      <div class="archive-row-copy"><h3>${pageLink(variant, "post", post.title)}</h3><p>${post.description}</p></div>
      <div class="archive-row-tags">${tagLinks(variant, post.tags)}</div>
      ${pageLink(variant, "post", "↗", "archive-open")}
    </article>
  `).join("");
}

function archivePage(variant, page) {
  if (page === "home") {
    const lead = POSTS[0];
    return `
      <section class="archive-hero">
        <div class="archive-hero-issue"><span>Latest issue</span><strong>#${lead.issue}</strong><time>${lead.date}</time></div>
        <div class="archive-hero-story"><p class="archive-kicker">TOOLS / FIELD REPORT</p><h1>${pageLink(variant, "post", lead.title)}</h1><p>${lead.description}</p><div>${tagLinks(variant, lead.tags)}</div></div>
        <aside class="archive-profile"><div>${avatarMarkup("archive-avatar")}<span class="archive-online">● ONLINE</span></div><p>${SITE.bio}</p><div>${externalLinks()}</div></aside>
      </section>
      <section class="archive-index" aria-labelledby="archive-recent"><header><p>RECENTLY FILED</p><h2 id="archive-recent">The latest from the archive</h2><span>05 / 33</span></header>${archiveRows(variant, POSTS.slice(1, 6))}<footer>${pageLink(variant, "blog", "OPEN THE COMPLETE INDEX →")}</footer></section>
    `;
  }
  if (page === "blog") {
    return `
      <section class="archive-page-banner"><div><p>COLLECTION / 01</p><h1>Blog</h1></div><p>33 篇公开记录<br>2023—2026<br>按创建时间倒序</p></section>
      <div class="archive-category-strip"><span class="is-active">ALL / 33</span><span>PYTHON / 15</span><span>TOOLS / 12</span><span>LIFE / 06</span></div>
      <section class="archive-index archive-full-index">${archiveRows(variant, POSTS)}<footer><span>PAGE 01 / 05</span><a href="#">NEXT PAGE →</a></footer></section>
    `;
  }
  if (page === "post") {
    const post = POSTS[0];
    return `
      <article class="archive-article">
        <header class="archive-article-head"><div class="archive-article-number"><span>FILE</span><strong>#${post.issue}</strong></div><div><p class="archive-kicker">${post.date} / 8 MIN READ</p><h1>${post.title}</h1><p>${post.description}</p><div class="archive-article-tags">${tagLinks(variant, post.tags)}</div></div></header>
        <div class="archive-article-layout"><aside><p>Filed under</p>${post.tags.map((tag) => `<span>${tag}</span>`).join("")}<hr><p>Contents</p><a href="#trace">Trace</a><a href="#parts">软件与插件</a><a href="#tradeoffs">Pros &amp; Cons</a></aside><div class="archive-prose">${articleBody(variant, "archive")}</div></div>
      </article>
      ${commentsPlaceholder(post.issue, "archive-comments")}
    `;
  }
  if (page === "ideas") return `<div class="archive-empty-wrap">${emptyIdeas(variant, "archive")}<aside><strong>IDEAS</strong><span>SHORT NOTES</span><span>UNPOLISHED</span><span>IN PROGRESS</span></aside></div>`;
  if (page === "projects") {
    return `
      <section class="archive-page-banner"><div><p>COLLECTION / 02</p><h1>Projects</h1></div><p>Curated, not scraped.<br>01 active project.</p></section>
      <article class="archive-project-poster"><div class="archive-project-no">P—01</div><div><p class="archive-kicker">PYTHON / ISSUE-BASED CMS</p><h2>escaping</h2><p>A minimalist and highly automated personal blog framework.</p><p class="archive-project-cn">把 GitHub Issues 变成内容源，把重复发布变成一次自动构建。</p><a href="https://github.com/geoqiao/escaping">VIEW SOURCE ↗</a></div><dl><div><dt>STARS</dt><dd>01</dd></div><div><dt>FORKS</dt><dd>02</dd></div><div><dt>LANG</dt><dd>PY</dd></div></dl></article>
    `;
  }
  if (page === "tags") {
    return `
      <section class="archive-page-banner"><div><p>INDEX / A—Z</p><h1>Tags</h1></div><p>${TAGS.length} visible labels<br>33 published posts</p></section>
      <div class="archive-tags-wall">${TAGS.map(([tag, count], index) => `<a href="${hrefFor(variant, "blog")}" data-page="blog" style="--rank:${Math.min(count, 8)}"><span>${String(index + 1).padStart(2, "0")}</span><strong>${tag}</strong><em>${count}</em></a>`).join("")}</div>
    `;
  }
  return `
    <article class="archive-about">
      <div class="archive-about-title"><p>PROFILE / ISSUE #42</p><h1>关于<br>geoqiao</h1><div class="archive-about-stamp">ABOUT<br>2026</div></div>
      <div class="archive-about-content"><div>${avatarMarkup("archive-about-avatar")}<p>CHENGDU, CN<br>STRATEGY / CODE / LIFE</p></div><div class="archive-prose"><p class="archive-lede">你好，我是 geoqiao。</p><p>我是一名金融行业的贷后策略分析师，喜欢折腾工具，也享受用代码解决重复性工作。</p><p>工作之余，我喜欢记录生活中的碎片。</p><h2>Find me elsewhere</h2><div class="archive-about-links">${externalLinks()}</div></div></div>
    </article>
    ${commentsPlaceholder(42, "archive-comments")}
  `;
}

function renderArchive(page) {
  const variant = "archive";
  return `
    <div class="direction direction-archive">
      <header class="archive-header">
        <div class="archive-topline"><span>ISSUE-BASED PERSONAL ARCHIVE</span><span>CHENGDU · CN / ${new Date().getFullYear()}</span><span>STRATEGY · TOOLS · FRAGMENTS</span></div>
        <div class="archive-masthead">${pageLink(variant, "home", "GEOQIAO", "archive-brand")}<p>Field notes from a strategy analyst<br>who would rather automate it.</p><div class="archive-mark">GQ<br><span>№ 41</span></div></div>
        ${archiveNavigation(variant, page)}
      </header>
      <main class="archive-main" id="prototype-main" tabindex="-1">${archivePage(variant, page)}</main>
      <footer class="archive-footer"><strong>GEOQIAO.ME</strong><span>BUILT FROM GITHUB ISSUES</span><span>© ${new Date().getFullYear()}</span><a href="https://github.com/geoqiao/escaping">SOURCE ↗</a></footer>
      <div class="archive-edge" aria-hidden="true">ISSUE ARCHIVE / SCROLL TO READ</div>
    </div>
  `;
}

function render() {
  const { variant, page, mode } = currentState();
  const ledgerVariant = isLedgerVariant(variant.slug);
  const modeSuffix = ledgerVariant && mode === "dark" ? " · Dark" : "";
  document.body.dataset.variant = variant.slug;
  document.body.dataset.mode = mode;
  app.innerHTML = ledgerVariant ? renderLedger(page, mode, variant.slug) : variant.slug === "workbench" ? renderWorkbench(page) : renderArchive(page);
  variantKey.textContent = variant.key;
  variantName.textContent = `${variant.name}${modeSuffix}`;
  document.title = `${PAGE_TITLES[page]} — ${variant.name}${modeSuffix} prototype`;
}

function setVariant(offset) {
  const { variant, page, mode } = currentState();
  const currentIndex = VARIANTS.findIndex((item) => item.slug === variant.slug);
  const nextIndex = (currentIndex + offset + VARIANTS.length) % VARIANTS.length;
  const next = VARIANTS[nextIndex];
  window.history.replaceState({}, "", hrefFor(next.slug, page, mode));
  render();
  window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

previousButton.addEventListener("click", () => setVariant(-1));
nextButton.addEventListener("click", () => setVariant(1));

app.addEventListener("click", (event) => {
  const modeToggle = event.target.closest("[data-ledger-mode]");
  if (modeToggle) {
    const { variant, page, mode } = currentState();
    const nextMode = mode === "dark" ? "light" : "dark";
    window.sessionStorage.setItem("ledger-mode", nextMode);
    window.history.replaceState({}, "", hrefFor(variant.slug, page, nextMode));
    render();
    return;
  }

  const link = event.target.closest("a[data-page]");
  if (!link) return;
  event.preventDefault();
  const { variant, mode } = currentState();
  window.history.pushState({}, "", hrefFor(variant.slug, link.dataset.page, mode));
  render();
  window.scrollTo({ top: 0, behavior: "auto" });
});

window.addEventListener("keydown", (event) => {
  const target = event.target;
  if (target instanceof HTMLElement && (target.matches("input, textarea, select") || target.isContentEditable)) return;
  if (event.key === "ArrowLeft") setVariant(-1);
  if (event.key === "ArrowRight") setVariant(1);
});

window.addEventListener("popstate", render);
render();
