(() => {
  "use strict";
  const root = document.documentElement;
  const mobile = matchMedia("(max-width: 760px)");
  const menu = document.querySelector(".menu-toggle");
  const panel = document.getElementById("navigation-panel");
  const themeToggle = document.querySelector(".theme-toggle");
  const system = matchMedia("(prefers-color-scheme: dark)");
  let choice;
  try { choice = localStorage.getItem("quiet-theme"); } catch { /* Private mode still works. */ }
  if (!["light", "dark"].includes(choice)) choice = null;

  function setAppearance(theme) {
    root.dataset.theme = theme;
    themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
  }
  setAppearance(choice || (system.matches ? "dark" : "light"));
  system.addEventListener("change", () => {
    if (!choice) setAppearance(system.matches ? "dark" : "light");
  });
  themeToggle.addEventListener("click", () => {
    choice = root.dataset.theme === "dark" ? "light" : "dark";
    setAppearance(choice);
    try { localStorage.setItem("quiet-theme", choice); } catch { /* Keep the in-memory choice. */ }
  });
  themeToggle.hidden = false;

  function closeMenu() {
    menu.setAttribute("aria-expanded", "false");
    panel.classList.remove("is-open");
  }
  menu.addEventListener("click", () => {
    const open = menu.getAttribute("aria-expanded") !== "true";
    menu.setAttribute("aria-expanded", String(open));
    panel.classList.toggle("is-open", open);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
      closeMenu();
      menu.focus();
    }
  });
  let lastFocused = document.activeElement;
  function dismissOutside(event) {
    if (event.type === "focusin") lastFocused = event.target;
    if (!panel.contains(event.target) && !menu.contains(event.target)) closeMenu();
  }
  document.addEventListener("pointerdown", dismissOutside);
  document.addEventListener("focusin", dismissOutside);
  mobile.addEventListener("change", () => {
    // CSS can hide the focused panel before the media-query event runs.
    const active = document.activeElement === document.body ? lastFocused : document.activeElement;
    closeMenu();
    if (mobile.matches && panel.contains(active)) menu.focus();
    if (!mobile.matches && active === menu) document.querySelector(".identity").focus();
  });
  menu.hidden = false;
  root.classList.add("js");

  const body = document.querySelector(".post-content");
  if (!body) return;
  const headings = [...body.querySelectorAll("h1, h2, h3")];
  const toc = document.querySelector("[data-toc]");
  if (headings.length && toc) {
    const links = headings.map((heading, index) => {
      if (!heading.id) {
        let id = heading.textContent.trim().toLowerCase()
          .replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-|-$/g, "") || `section-${index + 1}`;
        while (document.getElementById(id)) id += "-section";
        heading.id = id;
      }
      heading.tabIndex = -1;
      const link = document.createElement("a");
      link.href = `#${encodeURIComponent(heading.id)}`;
      link.textContent = heading.textContent;
      link.dataset.level = heading.tagName.slice(1);
      toc.appendChild(link);
      return link;
    });
    document.querySelector(".reading-margin").hidden = false;
    const details = document.querySelector(".toc");
    const compact = matchMedia("(max-width: 1180px)");
    details.open = !compact.matches;
    compact.addEventListener("change", () => { details.open = !compact.matches; });
    let scheduled = false;
    function updateLocation() {
      // ponytail: one scan per frame; use an observer if articles reach hundreds of headings.
      let active = 0;
      headings.forEach((heading, index) => {
        if (heading.getBoundingClientRect().top <= 160) active = index;
      });
      links.forEach((link, index) => {
        if (index === active) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
      scheduled = false;
    }
    window.addEventListener("scroll", () => {
      if (!scheduled) {
        scheduled = true;
        requestAnimationFrame(updateLocation);
      }
    }, { passive: true });
    updateLocation();
    if (location.hash) {
      let target;
      try { target = headings.find((heading) => heading.id === decodeURIComponent(location.hash.slice(1))); } catch { /* An invalid fragment is not a reading error. */ }
      window.addEventListener("load", () => { target?.scrollIntoView(); }, { once: true });
    }
  }

  body.querySelectorAll("pre, table").forEach((element) => {
    element.tabIndex = 0;
    if (element.tagName === "PRE") element.setAttribute("role", "region");
    element.setAttribute("aria-label", element.tagName === "TABLE"
      ? "Table, scroll horizontally"
      : element.querySelector(".language-mermaid") || element.classList.contains("mermaid")
        ? "Diagram, scroll horizontally"
        : "Code, scroll horizontally");
  });
  body.querySelectorAll("pre > code:not(.language-mermaid)").forEach((code) => {
    const bar = document.createElement("div");
    bar.className = "code-tools";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-code";
    button.textContent = "Copy code";
    button.setAttribute("aria-live", "polite");
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code.textContent);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Select the code to copy manually";
      }
    });
    bar.appendChild(button);
    code.parentElement.before(bar);
  });
})();
