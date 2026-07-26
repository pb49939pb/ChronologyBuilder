#!/usr/bin/env python3
"""
Confirms the detail-level slider in the actual UI sends the expected value and that the server
reflects it back correctly. Requires the dedicated test server (testing/start_test_server.sh).
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
ZIP_PATH = BASE / "sample_data" / "case_000_pdfs.zip"
APP_URL = "http://127.0.0.1:5051"


def run_with_slider(page, slider_value, expected_label):
    page.goto(f"{APP_URL}/review")
    page.set_input_files("#zipfile", str(ZIP_PATH))
    page.fill("#detail-slider", str(slider_value))
    page.click("#submit-btn")
    page.wait_for_selector("#results", state="visible", timeout=120_000)
    stats_text = page.locator("#stats").inner_text()
    ok = f"Detail: {expected_label}" in stats_text
    print(f"slider={slider_value} -> stats show '{expected_label}': {'OK' if ok else 'FAIL'} ({stats_text})")
    return ok


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})

        results = []
        for value, label in [(0, "brief"), (1, "standard"), (2, "detailed")]:
            results.append(run_with_slider(page, value, label))

        browser.close()
        print("PASS" if all(results) else "FAIL")
        return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
