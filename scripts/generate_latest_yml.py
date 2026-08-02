#!/usr/bin/env python3
"""Generates electron-updater's Windows update-metadata file (latest.yml) for an already-built NSIS
installer, given only the .exe path and version.

Why this exists: there's no CI that runs `electron-builder --publish` for Windows (see
DESKTOP_PACKAGING.md — Windows builds are produced manually, on whoever's real Windows hardware, then
the .exe/.exe.blockmap are uploaded to a GitHub Release by hand). electron-builder only auto-generates
latest.yml when its own publish flow runs; a plain `npm run dist` without `--publish` still writes it
locally next to the installer, but it's easy to forget to grab/upload that file too when copying
artifacts off a build machine by hand. Confirmed this actually happened for real: v0.0.12's GitHub
release shipped `Chronology.Builder.Setup.0.0.12.exe` with no `latest.yml` at all (only `latest-mac.yml`
was present, from the separately-built Mac release) — electron-updater's NsisUpdater looks specifically
for `latest.yml` and has nothing else to fall back to, so every Windows install's auto-update check
silently found nothing to update to. That's the exact bug reported: "auto-update didn't work, had to
manually download from GitHub instead."

Usage: python3 scripts/generate_latest_yml.py <path-to-installer.exe> <version>
  e.g. python3 scripts/generate_latest_yml.py "Chronology.Builder.Setup.0.0.13.exe" 0.0.13
Writes latest.yml next to the given .exe. Upload BOTH the .exe (and its .blockmap, if present) AND
this latest.yml to the GitHub Release — all three are required for Windows auto-update to work.
"""
import base64
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    exe_path = Path(sys.argv[1])
    version = sys.argv[2]
    if not exe_path.is_file():
        print(f"Not a file: {exe_path}")
        sys.exit(1)

    data = exe_path.read_bytes()
    sha512_b64 = base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
    size = len(data)
    release_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    filename = exe_path.name

    out_path = exe_path.parent / "latest.yml"
    out_path.write_text(
        f"version: {version}\n"
        f"files:\n"
        f"  - url: {filename}\n"
        f"    sha512: {sha512_b64}\n"
        f"    size: {size}\n"
        f"path: {filename}\n"
        f"sha512: {sha512_b64}\n"
        f"releaseDate: '{release_date}'\n"
    )
    print(f"Wrote {out_path}")
    print("Upload this file to the GitHub Release alongside the .exe and .exe.blockmap.")


if __name__ == "__main__":
    main()
