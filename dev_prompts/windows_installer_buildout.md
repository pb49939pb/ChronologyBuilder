# Prompt for Claude: build and verify the Windows installer for Chronology Builder

Paste this whole file as your prompt to Claude Code on the Windows machine. It's written to be
self-contained — you (Claude, reading this on Windows) have no memory of the Mac-side work that
produced this repo, so everything you need is below.

## What this project is

Chronology Builder (repo: `pb49939pb/ChronologyBuilder` on GitHub, currently public) is an on-prem
Flask + Electron desktop app that helps a nurse paralegal build cited medical chronologies from case
records for medical malpractice litigation, using a local LLM via Ollama. Everything runs on one
machine — no case data or PHI ever leaves it. **This is still a prototype: never use real case files
or PHI with it. Synthetic test data only, always.**

The real deployment target (see `TOWER_SETUP.md`) is a Windows PC — a dedicated, often air-gapped
"tower" running Flask + Ollama, reached by an Electron shell on the paralegal's own separate Windows
laptop over a private LAN. Everything you're building here needs to work with **zero internet access
after the one-time first-run model download** — see `DESKTOP_PACKAGING.md` for the full reasoning.

## What already exists and is already verified (on macOS, NOT yet on Windows)

The macOS build of this exact same installer pipeline is fully built, packaged, and cold-start
tested — see `TEST_RESULTS.md`'s two entries "Bundled, offline-capable installer built and verified
on macOS" and the versioning/logging/install-wizard entry right after it. Read both before starting;
they explain WHY things are built the way they are, not just what. The Windows build should be the
*exact same architecture*, just built with Windows-native binaries:

- `electron/main.js` already has all the Windows code paths written (`process.platform === "win32"`
  branches throughout) — this is genuinely believed to be correct, just never actually run on real
  Windows hardware. You are the first real test of this code, not the first time it's been written.
- `scripts/build_backend.py` already detects Windows automatically (`platform.system() == "Windows"`)
  and produces `electron/vendor/backend-win/` when run there — same script used for the Mac build.
- `electron/package.json`'s `build.win` config (NSIS target, `extraResources` pointing at
  `vendor/ollama-win/` and `vendor/backend-win/`) is already correct and doesn't need editing.
- `electron/vendor/` is gitignored (large, platform-specific build output — never committed; meant
  to become a GitHub Release asset once built and verified). You will be creating
  `electron/vendor/backend-win/` and `electron/vendor/ollama-win/` locally; they will NOT show up in
  `git status` as trackable, and that's correct, not a bug.

## Your job

1. Build `electron/vendor/backend-win/` (the frozen Python backend).
2. Build `electron/vendor/ollama-win/` (the bundled Ollama runtime).
3. Build the actual NSIS installer (`npm run dist`).
4. **Genuinely cold-start test it** — this is the part that actually matters, explained below.
5. Report back (to the human, and/or update `DESKTOP_PACKAGING.md`'s "Not yet done" section) with
   exactly what worked, what didn't, and what you had to change from the steps below to make it work
   — this document is a best-effort plan written on a different machine, not gospel. If Windows
   Ollama's install layout turns out to need something different than step 2 assumes, fix step 2's
   *actual outcome* to match reality and say so clearly, the same way the Mac build's real gotcha
   (below) was found by testing, not by guessing correctly upfront.

## Step 1: clone the repo and set up Python

```
git clone https://github.com/pb49939pb/ChronologyBuilder.git
cd ChronologyBuilder\webapp
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pyinstaller
```

(Public repo — plain HTTPS clone needs no authentication. You'll only need git credentials if you
want to push changes back, which isn't required for this task since `electron/vendor/` is
gitignored anyway.)

## Step 2: get EasyOCR's models onto this machine

`scripts/build_backend.py` bundles EasyOCR's pre-downloaded detection/recognition models
(`craft_mlt_25k.pth`, `english_g2.pth`, ~93MB total) from `%USERPROFILE%\.EasyOCR\model\` — they
need to already be there before you run the build script. Two ways to get them there:

- **Fastest**: run the app once (`.venv\Scripts\python.exe app.py`, then open `http://127.0.0.1:5050`
  in a browser and process any PDF with `pip install fpdf2` + a quick synthetic test file, or just
  trigger any OCR-fallback path) so EasyOCR downloads them itself on first use. Needs internet.
- **No internet needed**: copy the `.pth` files from a Mac/Linux machine that's already run this
  app once — they're plain PyTorch weight files, not compiled code, so they're fully portable across
  platforms. Put them at `%USERPROFILE%\.EasyOCR\model\craft_mlt_25k.pth` and `...\english_g2.pth`.

## Step 3: build the frozen backend

```
cd ChronologyBuilder
webapp\.venv\Scripts\python.exe scripts\build_backend.py
```

This should produce `electron\vendor\backend-win\` containing `chronology-builder-backend.exe` (plus
an `_internal\` folder with everything it needs — templates, static assets, prompts, the license
public key, the EasyOCR models, all bundled as PyInstaller "datas", see the script's own comments).

**If this fails or warns about missing imports**: `pyinstaller-hooks-contrib` (installed alongside
`pyinstaller` in step 1) already ships hooks for `torch`/`torchvision`/`easyocr` — on Mac this meant
the build worked cleanly with zero manual hidden-import configuration. If Windows needs something
extra (a DLL PyInstaller doesn't auto-detect, a different hidden-import), figure out what's actually
missing from the real error and add it to `scripts/build_backend.py`'s `--hidden-import`/
`--collect-submodules` args — don't guess blindly, look at the actual PyInstaller warning output.

**Verify it actually works standalone** before moving on — this matters, don't skip it:
```
cd electron\vendor\backend-win
set LAWFIRMAGENT_PORT=5099
set LAWFIRMAGENT_DATA_DIR=%TEMP%\lfa_win_test
chronology-builder-backend.exe
```
In another terminal: `curl http://127.0.0.1:5099/` should return a redirect to `/license` (this is
correct — no license token installed at that throwaway data dir yet). If it crashes or errors
instead, that's a real bug to fix here before continuing — check `%TEMP%\lfa_win_test\logs\` for a
same-day `.log` file with a full traceback (see `webapp/applog.py` — every unhandled exception gets
logged there, not just printed to a console no one's watching).

## Step 4: bundle Ollama — the step most likely to need a real fix, not just following instructions

Install Ollama normally first: https://ollama.com/download/windows (the normal installer, GUI
and all — you're not keeping the GUI, just harvesting its install directory).

**The real gotcha, discovered the hard way on macOS, almost certainly recurs here in some form**:
bundling just the single `ollama.exe` binary is NOT enough. On Mac, `ollama serve` started fine with
just the one binary, but every actual generate call failed with "llama-server binary not found,"
because Ollama's real Mac distribution ships a companion `llama-server` executable plus a dozen
`libggml-*`/`libllama*`/`libmtmd*` shared libraries and Apple-Silicon-specific `mlx_metal_v3/v4`
directories, all sitting *alongside* the main `ollama` binary in `Ollama.app/Contents/Resources/`.
The fix was bundling that ENTIRE directory, not just the one exe.

Windows almost certainly has an equivalent — probably a `llama-server.exe` plus some `.dll` files in
whatever directory the Windows installer actually puts Ollama in (commonly something under
`%LOCALAPPDATA%\Programs\Ollama\` — find the real path, don't assume). **Don't just copy
`ollama.exe` and move on. List that entire install directory's contents first**, then copy the WHOLE
thing to `electron\vendor\ollama-win\` (minus Ollama's own GUI/icon assets, which you don't need —
on Mac this was `.icns`/`.png` files specifically excluded). Confirm by actually running a real
`ollama pull`/generate call against the copied, standalone directory (not the original install)
before moving on — that's the only way to know you got the right set of files, the same way the Mac
gap was actually found (a real failed generate call, not a hunch).

## Step 5: build and install

```
cd electron
npm install
npm run dist
```

This produces an NSIS installer (`.exe`) under `electron\dist\`. Per `package.json`'s
`nsis.oneClick: false`, it should show a normal install wizard (Next/Next/Finish), not a silent
one-click install — confirm that's actually what happens.

Install it, then **launch it. Expect a Windows SmartScreen "unknown publisher" warning — this is
expected** (no code signing is set up yet, a known, deliberately-deferred gap — see
`DESKTOP_PACKAGING.md`'s Gatekeeper/SmartScreen section), click through it ("More info" → "Run
anyway"), not a bug to fix here.

## Step 6: the cold-start test that actually matters

The equivalent Mac verification (see `TEST_RESULTS.md`) is exactly this, and it's the one that
actually proves the packaging is correct — a build that merely "opens without crashing" is not
sufficient, because a stale-but-already-running dev server on the same port can silently mask a
completely broken bundled spawn path (this happened for real during the Mac build's first pass —
read that `TEST_RESULTS.md` entry for the full story before assuming a passing launch means it's
actually working).

1. Make sure nothing is already listening on port 5050 or 11434 (check via `netstat -ano | findstr
   "5050 11434"`, kill anything found) — a from-scratch test is only real if the ports were
   genuinely free beforehand.
2. Launch the installed app.
3. Confirm via Task Manager (or `tasklist`) that it spawned its OWN
   `chronology-builder-backend.exe` and its OWN `ollama.exe` (from inside the installed app's
   resources directory, not some other pre-existing copy) — not just that a window appeared.
4. First launch will need to actually pull the model (`llama3.1:8b`, ~4.7GB) — confirm the splash
   screen shows a real, moving percentage progress bar (see `main.js`'s `ensureModelPulled`, which
   streams Ollama's own `/api/pull` HTTP progress — if this shows a static "Downloading…" with no
   percentage instead, something regressed and needs fixing here, not just noted).
5. Once ready, actually process a real (synthetic!) test PDF through the app end to end — confirm a
   real chronology comes back, not just that the page loaded.
6. Quit and relaunch — confirm the second launch is fast (model already present, `ollama list`
   finds it, no re-download) and doesn't hang on the pull step again.

## When you're done

Update `DESKTOP_PACKAGING.md`'s "Not yet done / real open items before a real Windows build"
section — move whatever's now actually verified out of that list, and add a new dated entry (same
style as the macOS one) documenting what you found, especially:
- The exact contents of the Ollama Windows install directory you had to bundle (so this doesn't need
  re-discovering next time).
- Anything you had to change in `scripts/build_backend.py` or `electron/main.js` to make this work,
  and why.
- Whether SmartScreen's warning was the only friction point, or if something else came up.

If you find and fix a real bug in the shared (non-Windows-specific) code while doing this — say so
explicitly and explain the root cause, not just what changed, matching how bugs are documented
elsewhere in `TEST_RESULTS.md` in this repo.
