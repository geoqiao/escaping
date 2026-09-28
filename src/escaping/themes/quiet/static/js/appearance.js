(() => {
  let theme;
  try { theme = localStorage.getItem("quiet-theme"); } catch { /* Storage is optional. */ }
  const root = document.documentElement;
  root.dataset.theme = ["light", "dark"].includes(theme)
    ? theme : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

  // Wire navigation before first paint. Delegation works before the body exists;
  // a failed head script leaves the CSS-only, expanded navigation intact.
  const mobile = matchMedia("(max-width: 1160px)");
  function closeMenu() {
    document.querySelector(".menu-toggle")?.setAttribute("aria-expanded", "false");
    document.getElementById("navigation-panel")?.classList.remove("is-open");
  }
  document.addEventListener("click", (event) => {
    const menu = event.target.closest(".menu-toggle");
    if (!menu) return;
    const open = menu.getAttribute("aria-expanded") !== "true";
    menu.setAttribute("aria-expanded", String(open));
    document.getElementById("navigation-panel").classList.toggle("is-open", open);
  });
  document.addEventListener("keydown", (event) => {
    const menu = document.querySelector(".menu-toggle");
    if (event.key === "Escape" && menu?.getAttribute("aria-expanded") === "true") {
      closeMenu();
      menu.focus();
    }
  });
  let lastFocused;
  function dismissOutside(event) {
    if (event.type === "focusin") lastFocused = event.target;
    if (!event.target.closest(".navigation-panel, .menu-toggle")) closeMenu();
  }
  document.addEventListener("pointerdown", dismissOutside);
  document.addEventListener("focusin", dismissOutside);
  mobile.addEventListener("change", () => {
    const menu = document.querySelector(".menu-toggle");
    const panel = document.getElementById("navigation-panel");
    // CSS can hide the focused panel before the media-query event runs.
    const active = document.activeElement === document.body ? lastFocused : document.activeElement;
    closeMenu();
    if (mobile.matches && panel?.contains(active)) menu.focus();
    if (!mobile.matches && active === menu) document.querySelector(".identity")?.focus();
  });
  // Only advertise readiness after all menu handlers are installed. site.js is
  // optional for navigation; its failure must not leave an inert closed menu.
  root.classList.add("navigation-ready");
})();
