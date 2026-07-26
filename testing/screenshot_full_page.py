#!/usr/bin/env python3
"""Takes full-page screenshots (light and dark) for visual design review."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
ZIP_PATH = BASE / "sample_data" / "case_000_pdfs.zip"
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
APP_URL = "http://127.0.0.1:5051"


def main():
    run_analysis = "--with-results" in sys.argv
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for scheme in ["light", "dark"]:
            page = browser.new_page(viewport={"width": 1500, "height": 1100}, color_scheme=scheme)
            page.goto(f"{APP_URL}/review")

            if run_analysis:
                page.set_input_files("#zipfile", str(ZIP_PATH))
                page.click("#submit-btn")
                page.wait_for_selector("#results", state="visible", timeout=60_000)
                page.locator(".finding").first.click()
                page.wait_for_timeout(1000)

            out = SCREENSHOT_DIR / f"design_{scheme}{'_results' if run_analysis else ''}.png"
            page.screenshot(path=str(out), full_page=True)
            print(f"saved {out}")
            page.close()

        browser.close()


if __name__ == "__main__":
    main()
