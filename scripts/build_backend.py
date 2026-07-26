#!/usr/bin/env python3
"""
Freezes webapp/app.py + all its dependencies into a standalone executable via PyInstaller — no
system Python required on the machine that runs it. This is what closes the real gap found while
planning the bundled installer: the Electron app's packaged build previously spawned
`webapp/.venv/bin/python app.py`, which only works if that exact venv (tied to THIS machine's Python
install) happens to already exist at that path — never true on a genuinely fresh machine.

Bundles as PyInstaller "datas" everything app.py resolves via `_resource_path()` at runtime
(prompts/, templates/, static/, the pre-downloaded EasyOCR model weights, and the license public
key) — see app.py's `_resource_path()`/`_FROZEN` and license.py's copy of the same idiom for the
matching runtime-side lookup.

Usage: webapp/.venv/bin/python scripts/build_backend.py
Output: electron/vendor/backend-<platform>/  (an entire folder — PyInstaller "onedir" mode, not
        "onefile": onefile re-extracts everything to a temp dir on EVERY launch, which is slow and
        wasteful for a bundle this size once PyTorch is in it; onedir just runs in place.)
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = REPO_ROOT / "webapp"
PROMPTS_DIR = REPO_ROOT / "prompts"
EASYOCR_MODEL_DIR = Path.home() / ".EasyOCR" / "model"

PLATFORM_TAG = {"Darwin": "mac", "Windows": "win", "Linux": "linux"}.get(platform.system(), platform.system().lower())
OUTPUT_DIR = REPO_ROOT / "electron" / "vendor" / f"backend-{PLATFORM_TAG}"
BUILD_NAME = "chronology-builder-backend"

SEP = ";" if platform.system() == "Windows" else ":"  # PyInstaller --add-data separator


def main():
    if not EASYOCR_MODEL_DIR.is_dir():
        print(f"ERROR: {EASYOCR_MODEL_DIR} not found — run the app once so EasyOCR downloads its "
              f"detection/recognition models (~93MB), then re-run this build.", file=sys.stderr)
        return 1

    dist_path = REPO_ROOT / "electron" / "vendor" / "_pyinstaller_dist"
    work_path = REPO_ROOT / "electron" / "vendor" / "_pyinstaller_build"

    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", BUILD_NAME,
        "--onedir",
        "--noconfirm",
        "--clean",
        "--distpath", str(dist_path),
        "--workpath", str(work_path),
        "--add-data", f"{PROMPTS_DIR}{SEP}prompts",
        "--add-data", f"{WEBAPP_DIR / 'templates'}{SEP}templates",
        "--add-data", f"{WEBAPP_DIR / 'static'}{SEP}static",
        "--add-data", f"{WEBAPP_DIR / 'license_public_key.pem'}{SEP}.",
        "--add-data", f"{REPO_ROOT / 'VERSION'}{SEP}.",
        "--add-data", f"{EASYOCR_MODEL_DIR}{SEP}easyocr_models",
        "--hidden-import", "easyocr",
        "--collect-submodules", "docx",
        str(WEBAPP_DIR / "app.py"),
    ]
    print("Running:", " ".join(args))
    result = subprocess.run(args, cwd=str(WEBAPP_DIR))
    if result.returncode != 0:
        print("PyInstaller build failed.", file=sys.stderr)
        return result.returncode

    built_dir = dist_path / BUILD_NAME
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(built_dir), str(OUTPUT_DIR))
    print(f"\nFrozen backend written to: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
