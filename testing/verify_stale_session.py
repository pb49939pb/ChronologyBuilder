#!/usr/bin/env python3
"""Confirms that clicking a finding whose session PDFs were deleted (by a newer upload replacing
them) shows a clear 'session expired' message instead of a raw exception."""
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
ZIP_PATH = BASE / "sample_data" / "case_000_pdfs.zip"
APP_URL = "http://127.0.0.1:5051"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{APP_URL}/review")
        page.set_input_files("#zipfile", str(ZIP_PATH))
        page.click("#submit-btn")
        page.wait_for_selector("#results", state="visible", timeout=120_000)

        session_id = page.evaluate("""() => {
            const raw = sessionStorage.getItem('lawfirmagent_last_result');
            return raw ? JSON.parse(raw).session_id : null;
        }""")
        print(f"session_id: {session_id}")

        session_dir = Path(tempfile.gettempdir()) / "lawfirmagent_sessions_5051" / session_id
        if not session_dir.exists():
            print(f"FAIL: expected session dir not found at {session_dir}")
            return 1

        print(f"Deleting {session_dir} to simulate it being replaced by a newer upload...")
        shutil.rmtree(session_dir)

        page.wait_for_selector(".finding", timeout=10_000)
        # A plain row click is a lightweight selection only (doesn't touch the PDF viewer) — loading
        # the source, which is what actually needs to detect a deleted/replaced session, requires
        # the citation chip specifically (see the comment on it in makeFindingEl).
        page.locator(".finding-citation").first.click()
        page.wait_for_timeout(1500)

        title = page.locator("#viewer-title").inner_text()
        hint = page.locator("#viewer-hint").inner_text()
        print(f"viewer-title: {title!r}")
        print(f"viewer-hint: {hint!r}")

        ok = "expired" in title.lower() and "re-upload" in hint.lower()
        browser.close()
        print("PASS" if ok else "FAIL")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
