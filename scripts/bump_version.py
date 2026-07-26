#!/usr/bin/env python3
"""
Bumps this project's version. Single source of truth is the root `VERSION` file (plain text,
valid semver, e.g. "0.0.1-pre") — read by webapp/app.py at startup (via _resource_path(), so it
works identically in dev mode and a PyInstaller-frozen build) and mirrored into
electron/package.json's own "version" field, which electron-builder/electron-updater need to be
real semver for installer naming and update-version comparisons.

Usage:
    python scripts/bump_version.py patch   # 0.0.1-pre -> 0.0.2-pre  (drops a pre-release tag once bumped)
    python scripts/bump_version.py minor   # 0.0.1-pre -> 0.1.0
    python scripts/bump_version.py major   # 0.1.4     -> 1.0.0

Going from a pre-release to the real "1.0.0" launch version is a one-time event, not a fourth bump
kind — just edit VERSION by hand to "1.0.0" when that day comes.

A patch bump is meant to happen on every push to GitHub (see hooks/pre-push) in addition to however
often it's triggered manually — this script itself doesn't care which triggered it.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
ELECTRON_PACKAGE_JSON = REPO_ROOT / "electron" / "package.json"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$")


def parse_version(s: str) -> tuple:
    m = VERSION_RE.match(s.strip())
    if not m:
        raise ValueError(f"'{s}' is not a valid semver version (expected X.Y.Z or X.Y.Z-tag)")
    major, minor, patch, tag = m.groups()
    return int(major), int(minor), int(patch), tag


def bump(current: str, kind: str) -> str:
    major, minor, patch, tag = parse_version(current)
    if kind == "patch":
        # A pre-release tag on the CURRENT version means this is still pre-1.0 churn -- bump patch
        # and drop the tag, since the whole point of a patch bump is "this is now a newer, real
        # build," not "still the same pre-release, just relabeled." A non-pre-release patch bump
        # (already live) works the same way, just with no tag to drop.
        return f"{major}.{minor}.{patch + 1}"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"Unknown bump kind: {kind}")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("patch", "minor", "major"):
        print(__doc__)
        return 1

    current = VERSION_FILE.read_text().strip()
    new_version = bump(current, sys.argv[1])
    VERSION_FILE.write_text(new_version + "\n")

    package = json.loads(ELECTRON_PACKAGE_JSON.read_text())
    package["version"] = new_version
    ELECTRON_PACKAGE_JSON.write_text(json.dumps(package, indent=2) + "\n")

    print(f"{current} -> {new_version}")
    print(f"Updated: {VERSION_FILE}")
    print(f"Updated: {ELECTRON_PACKAGE_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
