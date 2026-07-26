// Electron main process for the Chronology Builder desktop shell.
//
// Two modes (see config.js): "local" spawns Flask + Ollama on this machine before showing them in
// a window (used here for dev/testing on macOS, and for a possible future single-machine build);
// "remote" spawns nothing and just points the window at an already-running instance elsewhere —
// the actual target setup, a dedicated "tower" reachable over a private, air-gapped wired link.
//
// NOT YET TESTED ON WINDOWS. This machine is macOS; the target user's machine is Windows. The
// mode="local" spawn logic below has a Windows branch, but the exact paths (a PyInstaller-built
// backend .exe, wherever Ollama's Windows installer actually places `ollama.exe`) are best-guess
// and marked accordingly — verify on real Windows hardware before relying on them. mode="remote"
// (the real target topology) doesn't spawn anything, so it isn't affected by that uncertainty at
// all — it just opens a window at a URL, which is platform-independent.
const { app, BrowserWindow, dialog, ipcMain, session } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const config = require("./config.js");
const applog = require("./applog.js");
const { autoUpdater } = require("electron-updater");

// Keeps the last few lines of a spawned child's stderr so a failure can be logged with actual
// diagnostic content instead of just "it exited" — capped since this is only ever used for the
// tail of a failure, not a general-purpose log capture (see applog.js for the real log).
function tailBuffer(maxLines = 20) {
  const lines = [];
  return {
    push(chunk) {
      for (const line of chunk.toString().split("\n")) {
        if (line.trim()) lines.push(line);
      }
      while (lines.length > maxLines) lines.shift();
    },
    get text() {
      return lines.join("\n");
    },
  };
}

let mainWindow = null;
let spawnedOllama = null; // only set if THIS process started it — never kill a pre-existing instance
let spawnedBackend = null;

function httpOk(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitUntilReady(url, { timeoutMs = 60_000, intervalMs = 500 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await httpOk(url)) return true;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}

function repoRoot() {
  // In dev this file lives at <repo>/electron/main.js; go up one level. Only ever used in dev
  // mode (app.isPackaged === false) — a packaged build has no such source tree to find.
  return path.resolve(__dirname, "..");
}

// Bundled binaries (see scripts/build_backend.py and DESKTOP_PACKAGING.md) live under
// electron/vendor/<name>-<platform>/ in this repo, and get copied to that same relative location
// under process.resourcesPath by electron-builder's `extraResources` config (package.json).
function vendorDir(name) {
  const platformTag = process.platform === "darwin" ? "mac" : process.platform === "win32" ? "win" : "linux";
  const base = app.isPackaged ? process.resourcesPath : path.join(repoRoot(), "electron", "vendor");
  return path.join(base, `${name}-${platformTag}`);
}

function getOllamaBinaryPath() {
  if (app.isPackaged) {
    return path.join(vendorDir("ollama"), process.platform === "win32" ? "ollama.exe" : "ollama");
  }
  // Dev mode — unchanged from before packaging existed.
  if (process.platform === "darwin") return "/Applications/Ollama.app/Contents/Resources/ollama";
  if (process.platform === "win32") return "ollama.exe"; // assumed already on PATH
  return "ollama";
}

function getOllamaModelsDir() {
  // A private, app-owned model directory — used ONLY in packaged mode (see getOllamaEnv), so a
  // packaged build never depends on or conflicts with a separately-installed system Ollama and
  // its own model storage (this dev machine's LaunchAgent-managed instance, for example).
  return path.join(app.getPath("userData"), "ollama-models");
}

function getOllamaEnv() {
  const env = { ...process.env, OLLAMA_NO_CLOUD: "1", OLLAMA_HOST: `127.0.0.1:${config.OLLAMA_PORT}` };
  if (app.isPackaged) env.OLLAMA_MODELS = getOllamaModelsDir();
  return env;
}

function ensureOllamaRunning() {
  return httpOk(`http://127.0.0.1:${config.OLLAMA_PORT}`).then(async (already) => {
    if (already) return true; // reuse whatever's already serving this port, packaged or not

    const stderrTail = tailBuffer();
    try {
      spawnedOllama = spawn(getOllamaBinaryPath(), ["serve"], { env: getOllamaEnv(), stdio: ["ignore", "ignore", "pipe"] });
      spawnedOllama.stderr?.on("data", (d) => stderrTail.push(d));
      spawnedOllama.on("error", (err) => applog.logEvent("ollama_spawn_error", "Failed to spawn Ollama", { level: "ERROR", error: err }));
    } catch (err) {
      applog.logEvent("ollama_spawn_error", "Failed to spawn Ollama", { level: "ERROR", error: err });
    }
    const ready = await waitUntilReady(`http://127.0.0.1:${config.OLLAMA_PORT}`);
    if (!ready) {
      applog.logEvent("ollama_start_timeout", "Ollama did not become ready in time", {
        level: "ERROR", context: { stderr_tail: stderrTail.text },
      });
    }
    return ready;
  });
}

// The ONE step that needs internet access, and only the first time: if the required model isn't
// already present (checked via `ollama list` against whichever instance ensureOllamaRunning just
// confirmed is up — bundled-private or pre-existing), pulls it. After this succeeds once, the
// model lives in getOllamaModelsDir() and every later launch's `ollama list` check finds it
// immediately — no network needed again, matching the air-gapped tower's actual requirement.
//
// Pulls via Ollama's own HTTP API (POST /api/pull, streamed NDJSON progress) rather than shelling
// out to `ollama pull` and scraping its human-formatted terminal output (a carriage-return-redrawn
// progress bar, not meant to be machine-parsed) — the HTTP API gives real structured
// {status, completed, total} lines, which is what actually lets the splash screen show a genuine
// percentage instead of guessing from regex on terminal text.
function ensureModelPulled(onProgress) {
  return new Promise((resolve) => {
    const cmd = getOllamaBinaryPath();
    const env = getOllamaEnv();
    const list = spawn(cmd, ["list"], { env });
    let listOutput = "";
    list.stdout?.on("data", (d) => { listOutput += d.toString(); });
    list.on("error", (err) => {
      applog.logEvent("ollama_list_failed", "Failed to check installed models", { level: "ERROR", error: err });
      resolve(false);
    });
    list.on("close", () => {
      if (listOutput.includes(config.MODEL_NAME)) {
        resolve(true);
        return;
      }
      applog.logEvent("model_pull_started", `Pulling model ${config.MODEL_NAME} (first run only)`);
      pullModelViaApi(config.MODEL_NAME, onProgress).then((ok) => {
        applog.logEvent(ok ? "model_pull_finished" : "model_pull_failed",
          ok ? "Model pull finished" : "Model pull failed", { level: ok ? "INFO" : "ERROR" });
        resolve(ok);
      });
    });
  });
}

function pullModelViaApi(modelName, onProgress) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ name: modelName, stream: true });
    const req = http.request(
      {
        host: "127.0.0.1", port: config.OLLAMA_PORT, path: "/api/pull", method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
      },
      (res) => {
        let buffer = "";
        res.on("data", (chunk) => {
          buffer += chunk.toString();
          const lines = buffer.split("\n");
          buffer = lines.pop(); // last (possibly incomplete) line stays in the buffer
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const progress = JSON.parse(line);
              if (progress.total && progress.completed && onProgress) {
                onProgress(Math.round((progress.completed / progress.total) * 100));
              }
              if (progress.error) {
                applog.logEvent("model_pull_error", progress.error, { level: "ERROR" });
              }
            } catch {
              // A non-JSON or partial line — ignore rather than treat as fatal, Ollama's own
              // stream occasionally sends a status-only line that doesn't match this shape.
            }
          }
        });
        res.on("end", () => resolve(res.statusCode < 400));
        res.on("error", (err) => {
          applog.logEvent("model_pull_stream_error", "Model pull stream errored", { level: "ERROR", error: err });
          resolve(false);
        });
      }
    );
    req.on("error", (err) => {
      applog.logEvent("model_pull_request_error", "Model pull request failed", { level: "ERROR", error: err });
      resolve(false);
    });
    req.write(body);
    req.end();
  });
}

function getBackendCommand() {
  if (app.isPackaged) {
    const dir = vendorDir("backend");
    const exeName = process.platform === "win32" ? "chronology-builder-backend.exe" : "chronology-builder-backend";
    return { cmd: path.join(dir, exeName), args: [], cwd: dir };
  }
  // Dev mode — unchanged from before packaging existed, on every platform (the old code had a
  // separate win32 branch here too, but it was only ever a placeholder for the now-real bundled
  // path above — dev mode itself was always identical across platforms).
  const root = repoRoot();
  return {
    cmd: path.join(root, "webapp", ".venv", "bin", "python"),
    args: ["app.py"],
    cwd: path.join(root, "webapp"),
  };
}

function ensureBackendRunning() {
  return httpOk(config.LOCAL_URL).then(async (already) => {
    if (already) return true;

    const { cmd, args, cwd } = getBackendCommand();
    const stderrTail = tailBuffer();
    try {
      spawnedBackend = spawn(cmd, args, {
        cwd,
        env: { ...process.env, LAWFIRMAGENT_BIND_HOST: "127.0.0.1", LAWFIRMAGENT_PORT: String(config.LOCAL_PORT) },
        stdio: ["ignore", "ignore", "pipe"],
      });
      spawnedBackend.stderr?.on("data", (d) => stderrTail.push(d));
      spawnedBackend.on("error", (err) => applog.logEvent("backend_spawn_error", "Failed to spawn backend", { level: "ERROR", error: err }));
    } catch (err) {
      applog.logEvent("backend_spawn_error", "Failed to spawn backend", { level: "ERROR", error: err });
    }
    const ready = await waitUntilReady(config.LOCAL_URL, { timeoutMs: 120_000 }); // model/backend cold start can be slow
    if (!ready) {
      applog.logEvent("backend_start_timeout", "Backend did not become ready in time", {
        level: "ERROR", context: { stderr_tail: stderrTail.text },
      });
    }
    return ready;
  });
}

const ICON_PATH = path.join(__dirname, "icon.png");

function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    title: "Chronology Builder",
    icon: ICON_PATH, // matters on Windows/Linux (taskbar); macOS's Dock icon is set separately below,
                      // since packaging (build.mac.icon in package.json) only applies to a built .app,
                      // never to a plain `electron .` dev run
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.js"), // exposes window.chronologyBuilder — see preload.js
    },
  });
  mainWindow.loadURL(url);

  // The web app uses target="_blank" links in a few places (dashboard.js/case.js's "View
  // chronology"/"Continue reviewing" links) — deliberately, so a plain browser keeps the
  // dashboard/status page open in its own tab while the chronology opens in a new one. Electron's
  // default handling of target="_blank" isn't "open a new tab" though — with no handler at all, it
  // spawns an entirely new native BrowserWindow, which looks like a second copy of the whole app.
  // Deny that and navigate this SAME window instead — one window total, just changing pages,
  // matching what "stay in the same tab" actually means for a single-window desktop app. This is
  // an Electron-shell-only fix; the target="_blank" markup itself stays untouched since it's still
  // correct behavior for anyone using the plain web app in a real browser.
  mainWindow.webContents.setWindowOpenHandler(({ url: targetUrl }) => {
    mainWindow.loadURL(targetUrl);
    return { action: "deny" };
  });

  if (app.isPackaged) checkForUpdates({ silent: true });
}

// --- Auto-update (electron-updater, GitHub Releases provider — see package.json's build.publish)
//
// Confirmed direction: silent best-effort check on launch (never blocks startup, never shown if it
// fails — the real deployment target is often air-gapped, so "no internet" is an ordinary, expected
// outcome here, not an error) plus a manual "Check for Updates" action (the version badge itself,
// clickable — see _version_badge.html/preload.js). Downloaded updates only ever install after
// explicit confirmation — never silently restart the app out from under someone mid-review.
function sendUpdateStatus(status, extra = {}) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("update-status", { status, ...extra });
  }
}

function checkForUpdates({ silent }) {
  autoUpdater.checkForUpdates().catch((err) => {
    applog.logEvent("update_check_failed", "Update check failed", { level: silent ? "INFO" : "WARNING", error: err });
    if (!silent) sendUpdateStatus("error", { message: "Couldn't check for updates — check your internet connection." });
  });
}

autoUpdater.on("checking-for-update", () => sendUpdateStatus("checking"));
autoUpdater.on("update-not-available", () => {
  applog.logEvent("update_not_available", "Already on the latest version");
  sendUpdateStatus("not-available");
});
autoUpdater.on("update-available", (info) => {
  applog.logEvent("update_available", `Update available: ${info.version}`, { context: { version: info.version } });
  sendUpdateStatus("available", { version: info.version });
});
autoUpdater.on("error", (err) => {
  applog.logEvent("update_error", "Update check/download errored", { level: "WARNING", error: err });
  sendUpdateStatus("error", { message: "Couldn't check for updates — check your internet connection." });
});
autoUpdater.on("download-progress", (progress) => {
  sendUpdateStatus("downloading", { percent: Math.round(progress.percent) });
});
autoUpdater.on("update-downloaded", (info) => {
  applog.logEvent("update_downloaded", `Update downloaded: ${info.version}`, { context: { version: info.version } });
  sendUpdateStatus("downloaded", { version: info.version });
  dialog.showMessageBox(mainWindow, {
    type: "info",
    buttons: ["Restart Now", "Later"],
    defaultId: 0,
    message: `Chronology Builder ${info.version} is ready to install.`,
    detail: "Restart now to finish updating, or continue working and update later.",
  }).then(({ response }) => {
    if (response === 0) autoUpdater.quitAndInstall();
  });
});

ipcMain.handle("check-for-updates", () => checkForUpdates({ silent: false }));

// A real inline DOM (not a reload-per-message data: URL, which flickers and can't animate) —
// installer-wizard-style progress for the one genuinely long first-run step (the model download),
// per the "non-technical people need to see this isn't frozen" install-wizard work.
const SPLASH_HTML = `<!doctype html><html><head><style>
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; display:flex; flex-direction:column;
         align-items:center; justify-content:center; height:100vh; margin:0; background:#f3ede1;
         color:#2b2420; padding:0 2rem; }
  #message { text-align:center; margin-bottom:0.9rem; font-size:0.95rem; }
  #track { width:280px; height:8px; border-radius:999px; background:rgba(43,36,32,0.12); overflow:hidden; display:none; }
  #fill { height:100%; width:0%; background:#7d2a3a; border-radius:999px; transition:width 0.2s ease; }
</style></head><body>
  <p id="message">Starting Chronology Builder&hellip;</p>
  <div id="track"><div id="fill"></div></div>
</body></html>`;

function createSplash() {
  const splash = new BrowserWindow({
    width: 480, height: 220, resizable: false, frame: false,
    webPreferences: { contextIsolation: true },
  });
  const loaded = splash.loadURL("data:text/html," + encodeURIComponent(SPLASH_HTML));
  const setMessage = async (message) => {
    await loaded;
    splash.webContents.executeJavaScript(
      `document.getElementById('message').textContent = ${JSON.stringify(message)};` +
      `document.getElementById('track').style.display = 'none';`
    ).catch(() => {}); // splash may already be closing — never let a UI update crash startup
  };
  const setProgress = async (percent) => {
    await loaded;
    splash.webContents.executeJavaScript(
      `document.getElementById('track').style.display = 'block';` +
      `document.getElementById('fill').style.width = '${percent}%';`
    ).catch(() => {});
  };
  return { window: splash, setMessage, setProgress };
}

async function start() {
  if (config.MODE === "remote") {
    createWindow(config.REMOTE_URL);
    return;
  }

  const splash = createSplash();
  splash.setMessage("Starting Chronology Builder");

  const ollamaOk = await ensureOllamaRunning();
  if (!ollamaOk) {
    splash.window.close();
    dialog.showErrorBox(
      "Chronology Builder",
      "Couldn't start the local model server (Ollama). Make sure it's installed and try again."
    );
    app.quit();
    return;
  }

  // First-run only (see ensureModelPulled) — every later launch's `ollama list` check finds the
  // model already present and this resolves immediately with no network access at all.
  let modelPullStarted = false;
  const modelOk = await ensureModelPulled((percent) => {
    if (!modelPullStarted) {
      modelPullStarted = true;
      splash.setMessage("Downloading the local AI model — one-time only, needs internet access");
    }
    splash.setProgress(percent);
  });
  if (!modelOk) {
    splash.window.close();
    dialog.showErrorBox(
      "Chronology Builder",
      "Couldn't download the required AI model. Check your internet connection and try again."
    );
    app.quit();
    return;
  }
  splash.setMessage("Starting Chronology Builder");

  const backendOk = await ensureBackendRunning();
  splash.window.close();
  if (!backendOk) {
    dialog.showErrorBox(
      "Chronology Builder",
      "The app's backend didn't start in time. Check the logs and try again."
    );
    app.quit();
    return;
  }

  createWindow(config.LOCAL_URL);
  applog.logEvent("app_started", "Application window opened");
}

// Blocks every outbound request the renderer (or anything else routed through Electron's default
// session) tries to make, except the app's own backend and GitHub's update-check/release-asset
// hosts. Two real network paths exist OUTSIDE this hook's reach and can't be governed by it: (1)
// Ollama's own subprocess, which makes its own HTTP calls to ollama.com during first-run model
// pull — a separate Go binary, entirely outside Chromium's network stack; (2) possibly
// electron-updater's checkForUpdates(), depending on whether its HTTP client issues requests
// through Electron's session or Node's own https module directly — unverified either way, so the
// GitHub hosts are listed defensively: harmless if the hook can't see that traffic, load-bearing
// if it can. See TEST_RESULTS.md for the empirical check of which is actually true.
function installNetworkAllowlist() {
  const backendUrl = config.MODE === "remote" ? config.REMOTE_URL : config.LOCAL_URL;
  const allowedHosts = new Set([
    new URL(backendUrl).host,
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
  ]);

  session.defaultSession.webRequest.onBeforeRequest(
    { urls: ["http://*/*", "https://*/*", "ws://*/*", "wss://*/*"] },
    (details, callback) => {
      const host = new URL(details.url).host;
      const allowed = allowedHosts.has(host);
      if (!allowed) {
        applog.logEvent(
          "network_request_blocked",
          `Blocked request to ${host}`,
          { level: "WARNING", context: { url: details.url } }
        );
      }
      callback({ cancel: !allowed });
    }
  );
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    // Only relevant to a plain `electron .` dev run — a packaged .app already gets this from
    // build.mac.icon in package.json (baked into the bundle itself, no runtime call needed).
    if (process.platform === "darwin" && app.dock) app.dock.setIcon(ICON_PATH);
    applog.cleanupOldLogs();
    installNetworkAllowlist();
    start();
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });

  // Standard macOS convention (same as VS Code, etc.): clicking the Dock icon when no window is
  // open should reopen one, rather than doing nothing — window-all-closed above deliberately
  // keeps the app running in the background on macOS specifically so this can happen.
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) start();
  });

  app.on("before-quit", () => {
    // Only tear down what THIS process started — never kill a pre-existing Ollama/backend that
    // was already running before this app launched (e.g. via the system LaunchAgent on macOS).
    if (spawnedBackend) spawnedBackend.kill();
    if (spawnedOllama) spawnedOllama.kill();
  });
}
