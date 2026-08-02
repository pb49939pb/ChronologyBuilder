# Feasibility: single-download, icon-click desktop app

Prompted by: "how feasible would it be to make this entire app something that could be downloaded
all together and just started with an icon on the desktop — including the model and everything —
and force everything to start up when the icon is clicked. Is this doable?"

## Decision (2026-07-22): building this as an Electron app

The target user is confirmed as a Windows PC (not this Mac), which changes the calculus from the
"recommended path" below in two ways: (1) the plain-shell-script `.app` approach was macOS-only and
would need to be rebuilt from scratch for Windows anyway, so it no longer has a head start; (2) the
actual target hardware topology (see `TOWER_SETUP.md`) is a dedicated headless "tower" doing the
heavy compute, with a lightweight client on her everyday laptop — Electron's cross-platform main
process handles "spawn locally" and "point at a remote URL" with the same code, just a config
change, which the plain-launcher approach doesn't give for free. Proceeding with Electron.

**Built and verified so far** (`electron/` in this repo — `package.json`, `config.js`, `main.js`):
- Two modes via `LAWFIRMAGENT_MODE` env var: `local` (spawns Flask + Ollama on this machine, used
  for dev/testing here) and `remote` (opens a window pointed at an already-running instance
  elsewhere — the real target topology, see `TOWER_SETUP.md`).
- Verified end-to-end on this Mac via Chrome DevTools Protocol (Electron's window isn't visible in
  a screenshot in this remote/headless dev environment, so verification used CDP + Playwright
  instead of a literal screenshot): cold-start spawn (killed the backend, relaunched Electron,
  confirmed it detected the backend was down, spawned `webapp/.venv/bin/python app.py` itself as a
  direct child process, waited for it to become ready, then showed the app); already-running
  detection (backend already up — no duplicate spawned, window opens immediately); a full upload →
  extraction → generation → results → PDF-highlight flow, working correctly inside the Electron
  window; single-instance locking; window resize (layer-alignment regression suite still passes
  inside Electron specifically, not just a regular browser).
- **Found and fixed a real bug in the process**: the PDF viewer failed to load inside Electron
  specifically (worked fine in a regular browser) — `TypeError: this[#Oa].getOrInsertComputed is
  not a function`, thrown from inside pdf.js's optional-content handling. Root cause: `getOrInsert`/
  `getOrInsertComputed` are a very new TC39 "Map upsert" proposal, new enough that even a
  current Electron 33.x's bundled Chromium doesn't have it yet, even though pdf.js 6.1.200 already
  calls it. This is the same bug *class* as the earlier Safari-polyfill work (`URL.parse`,
  `Promise.try`, etc.) — same file, `webapp/static/pdfjs-polyfills.mjs`, same fix pattern (add the
  missing method if absent). **This is the seventh distinct missing-recent-API polyfill** needed
  for this vendored pdf.js build — the file's own top comment already flags that a third or fourth
  should trigger reconsidering an older, more conservative pdf.js version instead of continuing to
  patch individually. Worth actually doing that reconsideration soon rather than waiting for an
  eighth.

**macOS packaged build verified 2026-07-25**: `npm run dist` (`electron-builder`, `mac`/`dmg`
target) successfully produces a real `Chronology Builder.app` bundle + `.dmg` — copied to
`/Applications/`, launched via `open` (the same path a double-click takes), confirmed it stays
running (previously, running via a bare `electron .` in a foreground terminal would die the moment
that terminal session closed — a real installed `.app` has no such dependency). Custom icon
(`icon.icns`) and product name ("Chronology Builder") both confirmed correct in the built bundle's
`Info.plist`. No code signing configured, so electron-builder logged "skipped macOS application
code signing" — fine for this single-machine personal-use build (no Gatekeeper quarantine flag gets
set on a locally-built, locally-copied `.app`, unlike one downloaded from the internet), but real
distribution to another machine later would need this addressed (see Gatekeeper/SmartScreen note
below).

**Not yet done / real open items before a real Windows build:**
- No Windows machine available to test on — everything above was verified on this Mac. `main.js`
  has a Windows code path (best-guess `ollama.exe` on PATH, a not-yet-built PyInstaller backend
  executable) explicitly marked as unverified in the code comments.
- The Python backend needs to actually be packaged as a Windows executable (PyInstaller or
  equivalent) — right now `main.js`'s Windows branch assumes a `lawfirmagent-backend.exe` that
  doesn't exist yet.
- `electron-builder`'s `win` target (NSIS installer) is configured in `package.json` but has never
  been run — needs a Windows machine or Windows CI to actually produce an installer.
- No code signing set up — same Gatekeeper-equivalent (Windows SmartScreen) friction discussed
  below applies on Windows too, and matters more here since the target machine is the tower/laptop
  she'll actually use, not a dev machine.

**To do the Windows build once real hardware is available** (`electron/vendor/` is gitignored —
build output, not committed source, see §"Bundled installer" below) — see
`dev_prompts/windows_installer_buildout.md` for the full, detailed walkthrough (written for a
fresh coding agent with no context on this machine); short version:
1. `cd webapp && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt pyinstaller`
2. Run the app once so EasyOCR downloads its models to `%USERPROFILE%\.EasyOCR\model\` (or copy
   that folder over from a machine where it's already been used).
3. `.venv\Scripts\python.exe ..\scripts\build_backend.py` → produces `electron/vendor/backend-win/`
   (mirrors the already-verified `backend-mac/` build — same script, platform-detected automatically).
4. Install Ollama normally (https://ollama.com/download/windows), then copy its ENTIRE install
   directory (not just `ollama.exe`) to `electron/vendor/ollama-win/` — **just the one binary is not
   enough**, confirmed the hard way on macOS: Ollama needs a companion `llama-server` executable
   plus several shared libraries sitting alongside the main binary, or every generate call fails
   with "llama-server binary not found." Windows almost certainly has the same requirement in its
   own form (a `llama-server.exe` + DLLs) — verify the actual installed directory's contents
   directly rather than assuming, the same way this was root-caused on Mac.
5. `npm run dist` (from `electron/`) — produces the NSIS installer via the `win.extraResources`
   config in `package.json`, which expects exactly the two directories built in steps 3-4.

**Critical, confirmed-the-hard-way requirement for uploading a Windows release: `latest.yml` is not
optional.** There's no CI that runs `electron-builder --publish`, so every release so far has been
built locally and its artifacts uploaded to the GitHub Release by hand — and `v0.0.12`'s release
shipped `Chronology.Builder.Setup.0.0.12.exe` (+ `.exe.blockmap`) with NO `latest.yml` at all (only
`latest-mac.yml`, from the separately-built Mac release, was present). `electron-updater`'s
`NsisUpdater` looks specifically for a file literally named `latest.yml` in the newest release and
has no fallback if it's missing — every Windows install's auto-update check silently found nothing
to update to, and the only way to actually get the new version was a manual download from the
Releases page. This is the exact bug a real user hit and reported (fixed after the fact by uploading
a correctly-generated `latest.yml` to the existing `v0.0.12` release — see git history/TEST_RESULTS.md
for 2026-08-02). `npm run dist` writes `latest.yml` locally next to the `.exe` — it's just easy to
forget to also grab/upload that file when copying artifacts off the build machine by hand. **Always
upload all three: the `.exe`, its `.blockmap`, and `latest.yml`.** If `latest.yml` was somehow lost
(built on a machine no longer available, etc.), regenerate it with `python3
scripts/generate_latest_yml.py <path-to-installer.exe> <version>` — it only needs the already-built
`.exe` itself (computes the sha512/size electron-updater checks, and reads the real filename
directly off the file you point it at rather than it being typed/guessed separately). Also worth
checking on any future release: `v0.0.11`'s `latest.yml` had `url`/`path` set to
`Chronology-Builder-Setup-0.0.11.exe` (hyphens) while the actually-uploaded asset was named
`Chronology.Builder.Setup.0.0.11.exe` (dots) — a filename mismatch from manual renaming somewhere in
that release's process, which would have 404'd the download even with `latest.yml` present.

**Verdict: yes, fully doable, no fundamental blocker.** This is a normal, well-trodden pattern for
local-AI desktop tools (LM Studio, GPT4All, Ollama's own Mac app all do a version of this). It's a
real but bounded packaging effort — roughly a few focused days of work, not a research problem —
and it directly strengthens the Phase 0 rollout story in `PRODUCT_DEFINITION.md` (whoever sets up
the actual dedicated workstation wouldn't need to manually install Python packages, Ollama, or pull
model weights by hand).

## What "everything" actually is, and how big it is

| Component | Size on this machine | Notes |
|---|---|---|
| Model weights (llama3.1:8b) | 4.6GB | Biggest single piece by far |
| Python + Flask + pdfplumber + easyocr/PyTorch | 747MB (current venv) | PyTorch (pulled in by easyocr) is most of this |
| Ollama server binary | ~100-300MB | Already MIT-licensed, redistributable |
| Everything else (app code, pdf.js, mermaid) | A few MB | Negligible |

**Total realistic download: ~5.5-6GB.** Large, but normal for this category of tool — comparable
to LM Studio or GPT4All's own bundles. Given the whole point of this project is avoiding any
internet dependency once deployed (HIPAA/no-egress requirement, `PRODUCT_DEFINITION.md` §7), I'd
bundle the model weights INTO the installer rather than having first-launch pull them from the
internet — bigger download, but it means the tool genuinely never needs a network connection, on
first run or ever after, which matches the actual security requirement better.

## The three pieces that need to start, and how

1. **Ollama server** — already solved. This project already runs it exactly this way today (see
   `~/Library/LaunchAgents/com.lawfirmagent.ollama.plist`): the bare `ollama serve` binary, no GUI
   menu-bar app needed, with `OLLAMA_NO_CLOUD=1` and `OLLAMA_HOST=127.0.0.1:11434` set explicitly.
   A packaged app would bundle this same binary + the model weights inside its own bundle and
   launch it pointed at its own private model directory (`OLLAMA_MODELS=<bundle>/models`) — so it
   doesn't depend on or interfere with any separately-installed Ollama.
2. **The Flask app** — needs a Python runtime + its dependencies (currently the `webapp/.venv`
   virtualenv). Options, in order of how much they change today's code:
   - **Bundle the venv directly** inside the app package and launch it with its own
     `.venv/bin/python app.py` — simplest, zero code changes, but ties the bundle to this exact
     machine's Python ABI/architecture (fine for "this Mac" or "this exact model of Mac," riskier
     for wide distribution across different macOS/chip versions).
   - **PyInstaller** (or similar) to freeze the app + all dependencies into a single
     self-contained executable, independent of any system Python — the standard tool for this,
     more portable across machines, small added build-configuration effort (mainly around
     PyTorch/easyocr, which PyInstaller sometimes needs explicit "hidden import" hints for).
3. **The browser tab** — the app is already a normal web app; the launcher just needs to open
   `http://127.0.0.1:5050` in the default browser once the server responds, rather than building a
   custom native window (Electron/Tauri). This avoids an entire extra layer of tooling and works
   fine, since the actual UI has no need to be inside a "native" window.

## The launcher (the actual "icon on the desktop")

A macOS `.app` bundle is just a folder with a specific structure — double-clicking it runs
whatever's at `Contents/MacOS/<name>`. That entry point can be a plain shell script that:
1. Checks if its bundled Ollama is already running (port already bound) — if not, starts it
   pointed at the bundle's own model directory, and polls until it responds.
2. Checks if the Flask app is already running — if not, starts it (via the bundled venv or
   PyInstaller binary), and polls until `http://127.0.0.1:5050/` responds.
3. Opens that URL in the default browser (`open http://127.0.0.1:5050`).
4. If the user double-clicks the icon again while everything's already running, steps 1-2 are
   no-ops (ports already bound) and it just re-opens/refocuses the browser tab — no duplicate
   servers, no port conflicts.

This is genuinely simple — a ~30-40 line shell script, no compiled code, no Xcode project needed.
The icon itself is just a `.icns` file referenced in the bundle's `Info.plist`.

## The one real friction point: Gatekeeper / code signing

macOS blocks running an unsigned app downloaded from outside the App Store by default ("app is
damaged and can't be opened" / "unidentified developer"). This matters differently depending on who
the app is for:

- **Just this machine, or a small number of machines you personally control** (e.g. setting up the
  actual firm workstation yourself): a one-time right-click → Open (or a `System Settings` →
  Privacy & Security exception) bypasses this permanently for that copy of the app. No paid
  account needed, no extra build step.
- **Distributing to other people's Macs without you present to click through it**: needs an Apple
  Developer account ($99/year) to code-sign and notarize the app, or everyone hits the same
  scary warning on first launch. Given this tool's actual rollout plan is "one dedicated
  workstation, set up once" (not distributed to many separate machines), this likely doesn't
  matter in practice — worth confirming against the real rollout plan before treating it as a
  blocker.

## Recommended path

Given the actual near-term use case (this dev machine now, one dedicated workstation later, not
mass distribution): skip PyInstaller and code signing/notarization for now — bundle the existing
venv directly, write the ~30-line launcher shell script, wrap it in a minimal `.app` structure with
a custom icon, and bundle Ollama's binary + the model weights inside it. That's a genuinely small
effort (a day or so) and gets the actual "one icon, one click, everything starts" experience asked
for. Revisit PyInstaller/notarization only if this needs to go to a machine you won't be physically
present to unlock the first time.

## Open question worth resolving before building this

Is this meant to replace the current LaunchAgent-based always-running Ollama setup, or coexist with
it? A bundled app with its own private Ollama instance + model directory avoids fighting over ports/
model storage with the system-wide LaunchAgent already configured on this machine — recommend the
bundled app run Ollama on a distinct port (e.g. `127.0.0.1:11435`) from the existing LaunchAgent
setup (`11434`) if both need to coexist during development, or replace the LaunchAgent entirely if
this bundle becomes the only way this app gets used going forward.
