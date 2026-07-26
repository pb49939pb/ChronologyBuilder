// pdf.worker.min.mjs (vendored, unmodified) internally uses several very recent JS/web-platform
// additions not available in every browser yet. A worker's global scope is isolated from the main
// page, so the polyfills applied in app.js don't reach in here — this file exists specifically to
// cover that separate execution context before loading the real worker script.
//
// The polyfill import is a static import (runs first, since it's the only thing before the dynamic
// import below), but loading the real worker script uses a *dynamic* import deliberately: a static
// `import "./pdf.worker.min.mjs"` here would be evaluated before this file's own top-level code
// regardless of where it's textually written (that's how ES module evaluation order works), which
// could run pdf.worker.min.mjs before the polyfills are actually in place. Top-level await on a
// dynamic import guarantees the polyfills apply first.
import "../pdfjs-polyfills.mjs";

await import("./pdf.worker.min.mjs");
