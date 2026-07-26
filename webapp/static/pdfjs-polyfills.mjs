// Shared polyfills for very recent (2024-2025) JS/web-platform additions that the vendored pdf.js
// 6.1.200 build uses internally, but that aren't available in every browser yet. Imported by both
// app.js (main thread) and pdf.worker.polyfill.mjs (the worker's separate global scope, which a
// main-thread polyfill can't reach on its own).
//
// Each one has shown up as a separate "X is not a function" runtime error as different pdf.js code
// paths got exercised — if a browser is missing this many 2024-2025 additions, expect more to
// surface. If a third or fourth distinct one shows up, it's worth reconsidering whether to vendor
// an older, more conservative pdf.js version instead of continuing to patch individually.

if (typeof URL.parse !== "function") {
  URL.parse = function (url, base) {
    try {
      return new URL(url, base);
    } catch {
      return null;
    }
  };
}

if (typeof Promise.try !== "function") {
  // Promise.try(fn, ...args) calls fn(...args) and wraps the result — including a synchronous
  // throw — in a promise. Returning fn's result from the executor lets the Promise constructor's
  // own built-in try/catch handle a synchronous throw correctly.
  Promise.try = function (fn, ...args) {
    return new Promise((resolve) => resolve(fn(...args)));
  };
}

if (typeof Promise.withResolvers !== "function") {
  Promise.withResolvers = function () {
    let resolve, reject;
    const promise = new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}

if (typeof AbortSignal.any !== "function") {
  AbortSignal.any = function (signals) {
    const controller = new AbortController();
    for (const signal of signals) {
      if (signal.aborted) {
        controller.abort(signal.reason);
        break;
      }
      signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
    }
    return controller.signal;
  };
}

if (typeof Uint8Array.prototype.toHex !== "function") {
  Uint8Array.prototype.toHex = function () {
    return Array.from(this, (b) => b.toString(16).padStart(2, "0")).join("");
  };
}

if (typeof Uint8Array.prototype.toBase64 !== "function") {
  Uint8Array.prototype.toBase64 = function () {
    let binary = "";
    for (const b of this) binary += String.fromCharCode(b);
    return btoa(binary);
  };
}

if (typeof Uint8Array.fromBase64 !== "function") {
  // Static method (unlike toHex/toBase64, which are instance methods) — mirrors Array.from.
  Uint8Array.fromBase64 = function (base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  };
}

// Map/WeakMap.prototype.getOrInsert(Computed) — the TC39 "upsert" proposal (tc39/proposal-upsert),
// new enough that even a very recent Electron/Chromium build (33.x, tested 2026-07-22) doesn't
// have it yet. pdf.js's optional-content (layers) handling calls getOrInsertComputed internally —
// this is the SEVENTH distinct missing-recent-API polyfill needed for this vendored pdf.js build.
// Per the note at the top of this file: this is well past the "reconsider an older pdf.js version
// instead" threshold — worth doing if another one shows up.
for (const Ctor of [Map, WeakMap]) {
  if (typeof Ctor.prototype.getOrInsert !== "function") {
    Ctor.prototype.getOrInsert = function (key, value) {
      if (this.has(key)) return this.get(key);
      this.set(key, value);
      return value;
    };
  }
  if (typeof Ctor.prototype.getOrInsertComputed !== "function") {
    Ctor.prototype.getOrInsertComputed = function (key, callbackFn) {
      if (this.has(key)) return this.get(key);
      const value = callbackFn(key);
      this.set(key, value);
      return value;
    };
  }
}
