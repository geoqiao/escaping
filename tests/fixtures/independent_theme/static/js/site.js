(() => {
  const root = document.documentElement;
  root.classList.remove("no-js");
  root.classList.add("js");

  const button = document.querySelector("[data-theme-toggle]");
  if (!button) return;

  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let saved = null;
  try {
    saved = window.localStorage.getItem("theme");
  } catch (_) {
    saved = null;
  }
  const initial = saved === "light" || saved === "dark" ? saved : system.matches ? "dark" : "light";

  const apply = (theme) => {
    root.dataset.theme = theme;
    const dark = theme === "dark";
    button.textContent = dark ? "Use light theme" : "Use dark theme";
    button.setAttribute("aria-label", dark ? "Use light theme" : "Use dark theme");
    button.setAttribute("aria-pressed", dark ? "true" : "false");
  };

  button.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    try {
      window.localStorage.setItem("theme", next);
    } catch (_) {
      // The visual toggle still works when storage is unavailable.
    }
    apply(next);
  });

  apply(initial);
  button.hidden = false;
})();
