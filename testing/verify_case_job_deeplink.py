#!/usr/bin/env python3
"""
Confirms the dashboard's "/case?job=<job_id>" deep link actually works -- opening the case status
page in a FRESH browser tab that never itself started that job (the exact scenario the dashboard
relies on: clicking a historical case's "View status" link from a different tab/session than the
one that originally kicked it off). Before this URL-param support was added to case.js, the status
page only ever resumed whatever job THIS tab's own sessionStorage remembered starting -- a deep
link from elsewhere had no way to open a specific job at all.

Starts a real (small, single-document) case via POST /case/start directly, then verifies a second,
independent browser context (simulating a different tab/session) can open that exact job via the
URL param alone.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_case_job_deeplink.py [--headed]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from case_upload_helpers import urllib_start_case

APP_URL = "http://127.0.0.1:5051"
BASE = Path(__file__).resolve().parent.parent
CASE_FOLDER = BASE / "sample_data" / "case_000_pdfs"


def start_case() -> str:
    """POSTs /case/start directly (no browser needed for this part) and returns the job_id."""
    return urllib_start_case(APP_URL, "Deeplink Test Plaintiff", CASE_FOLDER)


def main():
    headed = "--headed" in sys.argv
    if not CASE_FOLDER.is_dir():
        print(f"FAIL: {CASE_FOLDER} does not exist on this machine — can't run this test")
        return 1

    job_id = start_case()
    print(f"started job via POST /case/start directly: {job_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            ok = run_checks(browser, job_id)
        finally:
            browser.close()
    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def run_checks(browser, job_id: str) -> bool:
    all_ok = True

    # A brand new browser context has empty sessionStorage -- nothing to resume from except the
    # URL param. This is the actual scenario a dashboard deep link produces (a different tab than
    # whichever one originally started the case).
    context = browser.new_context()
    page = context.new_page()
    console_errors = []
    page.on("pageerror", lambda e: console_errors.append(f"[PAGEERROR] {e}"))
    page.on("console", lambda m: console_errors.append(f"[console.error] {m.text}") if m.type == "error" else None)

    page.goto(f"{APP_URL}/case?job={job_id}")
    page.wait_for_selector("#job-view", state="visible", timeout=15_000)

    job_view_visible = page.locator("#job-view").is_visible()
    summary_text = page.locator("#job-summary").inner_text()
    plaintiff_shown = "Deeplink Test Plaintiff" in summary_text
    print(f"job-view visible: {job_view_visible}")
    print(f"job-summary text: {summary_text!r}")
    print(f"correct plaintiff name shown (proves the RIGHT job loaded via URL param, not some "
          f"other/no job): {plaintiff_shown}")

    ok = job_view_visible and plaintiff_shown
    print(f"-> {'PASS' if ok else 'FAIL'} (deep link opened the specific job passed in ?job=)\n")
    all_ok &= ok

    # sessionStorage should also now remember this job -- so a page refresh (still the same tab)
    # keeps showing it, same as if the tab had started it normally.
    stored_job_id = page.evaluate("() => sessionStorage.getItem('lawfirmagent_case_job_id')")
    storage_ok = stored_job_id == job_id
    print(f"sessionStorage now remembers this job: {storage_ok} ({stored_job_id!r})")
    print(f"-> {'PASS' if storage_ok else 'FAIL'}\n")
    all_ok &= storage_ok

    if console_errors:
        print(f"Console errors seen during run ({len(console_errors)}):")
        for e in console_errors[:10]:
            print(f"  - {e}")
        all_ok = False
    else:
        print("No console errors during run.")

    context.close()
    return all_ok


if __name__ == "__main__":
    sys.exit(main())
