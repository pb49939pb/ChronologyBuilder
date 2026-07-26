import mermaid from "./mermaid/mermaid.esm.min.mjs";

const isDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;

mermaid.initialize({
  startOnLoad: true,
  theme: isDark ? "dark" : "default",
  securityLevel: "strict",
  flowchart: { htmlLabels: true },
});
