(() => {
  let theme;
  try { theme = localStorage.getItem("quiet-theme"); } catch { /* Storage is optional. */ }
  document.documentElement.dataset.theme = ["light", "dark"].includes(theme)
    ? theme : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
})();
