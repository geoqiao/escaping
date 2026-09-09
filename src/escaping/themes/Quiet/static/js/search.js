(() => {
  "use strict";
  const script = document.querySelector("script[data-search-index]");
  const dialog = document.querySelector("#site-search");
  const trigger = document.querySelector(".search-toggle");
  if (!script || !dialog || !trigger || typeof dialog.showModal !== "function") return;

  const query = dialog.querySelector("#search-query");
  const results = dialog.querySelector(".search-results");
  const status = dialog.querySelector(".search-status");
  const error = dialog.querySelector(".search-error");
  let items = null;
  let pending = null;
  let returnFocus = null;
  let composing = false;
  const normalize = value => value.normalize("NFKC").toLowerCase();

  function validItem(item) {
    if (!item || typeof item.title !== "string" || typeof item.description !== "string"
      || !["Blog", "Idea", "Project"].includes(item.type)
      || !Array.isArray(item.tags) || !item.tags.every(tag => typeof tag === "string")
      || typeof item.url !== "string") return false;
    // Even a malformed/replaced static response must not create executable links.
    if (!/^(https:\/\/|\/(?!\/))/.test(item.url) || /[\s\\\u0000-\u001f]/u.test(item.url)) return false;
    try {
      const url = new URL(item.url, location.origin);
      return !url.username && !url.password
        && (item.url.startsWith("/") ? url.origin === location.origin : url.protocol === "https:");
    } catch { return false; }
  }

  function render() {
    if (items === null) return;
    const words = normalize(query.value).trim().split(/\s+/u).filter(Boolean);
    const ranked = items.map(item => {
      const title = normalize(item.title);
      const tags = normalize(item.tags.join(" "));
      const description = normalize(item.description);
      let score = 0;
      for (const word of words) {
        if (title.includes(word)) score += 3;
        else if (tags.includes(word)) score += 2;
        else if (description.includes(word)) score += 1;
        else return null;
      }
      return { item, score };
    }).filter(Boolean).sort((a, b) => b.score - a.score);
    results.replaceChildren();
    for (const { item } of ranked.slice(0, 20)) {
      const li = document.createElement("li");
      const link = document.createElement("a");
      link.href = item.url;
      for (const [className, text] of [
        ["search-result-type", item.type],
        ["search-result-title", item.title],
        ["search-result-description", item.description],
      ]) {
        const span = document.createElement("span");
        span.className = className;
        span.textContent = text;
        link.append(span);
      }
      li.append(link);
      results.append(li);
    }
    results.scrollTop = 0;
    if (!items.length) status.textContent = "No published content to search yet.";
    else if (!ranked.length) status.textContent = "No results. Try a title, topic or project name.";
    else if (!words.length) status.textContent = "Browse recent writing, ideas and projects.";
    else status.textContent = `${ranked.length} result${ranked.length === 1 ? "" : "s"}${ranked.length > 20 ? " · Showing the first 20; refine your search" : ""}.`;
  }

  function load() {
    if (items !== null) { render(); return; }
    if (pending) return;
    error.hidden = true;
    status.textContent = "Loading search…";
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10_000);
    pending = (async () => {
      try {
        const response = await fetch(script.dataset.searchIndex, {
          signal: controller.signal, credentials: "omit", mode: "same-origin",
        });
        if (!response.ok) throw new Error("Search unavailable");
        const data = await response.json();
        if (data?.version !== 1 || !Array.isArray(data.items) || !data.items.every(validItem)) {
          throw new Error("Invalid search index");
        }
        items = data.items;
        render();
      } catch {
        status.textContent = "Could not load search. Retry or browse the archives.";
        error.hidden = false;
      } finally {
        clearTimeout(timer);
        pending = null;
      }
    })();
  }

  function open(event) {
    if (!dialog.open) {
      returnFocus = event?.currentTarget === trigger || document.activeElement === document.body
        ? trigger : document.activeElement;
      dialog.showModal();
      document.documentElement.classList.add("search-open");
    }
    query.focus();
    load();
  }

  trigger.hidden = false;
  const shortcut = trigger.querySelector("[data-search-shortcut]");
  if (shortcut) shortcut.textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘ K" : "Ctrl K";
  trigger.addEventListener("click", open);
  dialog.querySelector(".search-close").addEventListener("click", () => dialog.close());
  dialog.querySelector(".search-retry").addEventListener("click", () => { load(); query.focus(); });
  dialog.querySelector("form").addEventListener("submit", event => {
    event.preventDefault();
    if (!composing) results.querySelector("a")?.click();
  });
  query.addEventListener("compositionstart", () => { composing = true; });
  query.addEventListener("compositionend", () => { composing = false; render(); });
  query.addEventListener("input", () => { if (!composing) render(); });
  dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right
      || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  dialog.addEventListener("close", () => {
    document.documentElement.classList.remove("search-open");
    const fallback = document.querySelector(".menu-toggle") || trigger;
    if (returnFocus?.isConnected && returnFocus.getClientRects().length) returnFocus.focus();
    else if (fallback.getClientRects().length) fallback.focus();
  });
  dialog.addEventListener("keydown", event => {
    if (composing || event.isComposing) return;
    if (event.key === "Escape") {
      // type=search otherwise consumes Escape to clear a populated input first.
      event.preventDefault();
      dialog.close();
      return;
    }
    if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
    const links = [...results.querySelectorAll("a")];
    const index = links.indexOf(document.activeElement);
    if (!links.length || (document.activeElement !== query && index < 0)) return;
    event.preventDefault();
    if (event.key === "ArrowDown") links[Math.min(index + 1, links.length - 1)].focus();
    else if (index <= 0) query.focus();
    else links[index - 1].focus();
  });
  document.addEventListener("keydown", event => {
    if (event.isComposing || event.altKey || !(event.metaKey || event.ctrlKey)
      || event.key.toLowerCase() !== "k") return;
    if (event.target.closest("input, textarea, [contenteditable]")) return;
    event.preventDefault();
    open();
  });
  // A back/forward-cache restore must not reopen an old modal or keep scroll locked.
  window.addEventListener("pagehide", () => {
    if (dialog.open) dialog.close();
    document.documentElement.classList.remove("search-open");
  });
})();
