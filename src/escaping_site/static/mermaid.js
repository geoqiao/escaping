(() => {
  "use strict";

  const loader = document.currentScript;
  const codeBlocks = [...document.querySelectorAll("pre code.language-mermaid")];
  const runtimeSrc = loader?.dataset.runtimeSrc;
  if (!loader || !runtimeSrc || !codeBlocks.length) return;

  const runtime = document.createElement("script");
  runtime.src = runtimeSrc;
  runtime.addEventListener("load", () => {
    const api = globalThis.mermaid;
    if (!api) return;

    const nodes = codeBlocks.map((code) => {
      const pre = code.parentElement;
      pre.className = "mermaid";
      pre.textContent = code.textContent;
      return pre;
    });
    const configuredTheme = loader.dataset.mermaidTheme;
    const theme = configuredTheme === "auto"
      ? (document.documentElement.dataset.theme === "dark" ? "dark" : "default")
      : (configuredTheme || "default");

    api.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme,
    });
    void api.run({ nodes }).catch(() => {
      // Mermaid renders its own syntax error; avoid an unhandled rejection.
    });
  });
  document.head.appendChild(runtime);
})();
