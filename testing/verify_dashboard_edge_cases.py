#!/usr/bin/env python3
"""
Covers dashboard.js branches that verify_dashboard.py's happy-path check doesn't reach: the
empty-state message (no cases at all), a fetch failure, and a case row with a failed secondary
group alongside a ready primary group (the "N groups failed" extra link). Mocks the /case/jobs
response via Playwright route interception -- deterministic, no LLM call and no dependency on
whatever real case history happens to exist on this machine.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_dashboard_edge_cases.py [--headed]
"""
import sys

from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:5051"


def mock_jobs(page, jobs, status=200):
    def handler(route):
        if status == 200:
            route.fulfill(status=200, content_type="application/json", body=__import__("json").dumps(jobs))
        else:
            route.fulfill(status=status, content_type="application/json", body="{}")
    page.route("**/case/jobs", handler)


def main():
    headed = "--headed" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            ok = run_checks(browser)
        finally:
            browser.close()
    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def run_checks(browser) -> bool:
    all_ok = True

    # --- Scenario 1: no cases at all -> clear empty-state message, CTA still prominent. ---
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    mock_jobs(page, [])
    page.goto(APP_URL)
    page.wait_for_timeout(400)
    empty_shown = page.locator(".case-list-empty").count() > 0
    empty_text = page.locator(".case-list-empty").inner_text() if empty_shown else ""
    cta_still_visible = page.locator(".new-case-cta").is_visible()
    print(f"[empty state] shown: {empty_shown}, text: {empty_text!r}, CTA still visible: {cta_still_visible}")
    ok1 = empty_shown and "no cases yet" in empty_text.lower() and cta_still_visible
    print(f"-> {'PASS' if ok1 else 'FAIL'}\n")
    all_ok &= ok1
    page.close()

    # --- Scenario 2: /case/jobs itself fails -> a clear error, not a silently blank panel. ---
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    mock_jobs(page, [], status=500)
    page.goto(APP_URL)
    page.wait_for_timeout(400)
    error_shown = page.locator(".case-list-empty").count() > 0
    error_text = page.locator(".case-list-empty").inner_text() if error_shown else ""
    print(f"[fetch failure] message shown: {error_shown}, text: {error_text!r}")
    ok2 = error_shown and "couldn't load" in error_text.lower()
    print(f"-> {'PASS' if ok2 else 'FAIL'}\n")
    all_ok &= ok2
    page.close()

    # --- Scenario 3: a done case whose primary group is ready but ALSO has a failed secondary
    # group -> must show BOTH "Continue reviewing" (the primary action) AND a distinct "View case
    # status" link surfacing the failure, not silently hide it just because the main group is fine.
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    mock_jobs(page, [{
        "job_id": "fake-job-1",
        "folder": "/fake/path",
        "plaintiff_name": "Jane Edgecase",
        "defendant_names": ["Dr. Edge Case"],
        "dol": "01/01/2026",
        "status": "done",
        "started_at": 1784864337.0,
        "finished_at": 1784864537.0,
        "total_documents": 12,
        "group_count": 2,
        "failed_group_count": 1,
        "primary_group_key": "janeedgecase",
        "primary_group_ready": True,
    }])
    page.goto(APP_URL)
    page.wait_for_timeout(400)
    row_text = page.locator(".case-row").first.inner_text()
    print(f"[failed secondary group] row text: {row_text!r}")
    has_continue = "continue reviewing" in row_text.lower()
    has_extra_status_link = "view case status" in row_text.lower()
    has_failed_note = "1 group" in row_text.lower() and "failed" in row_text.lower()
    print(f"has 'Continue reviewing': {has_continue}, has extra 'View case status' link: "
          f"{has_extra_status_link}, meta line mentions the failed group: {has_failed_note}")
    ok3 = has_continue and has_extra_status_link and has_failed_note
    print(f"-> {'PASS' if ok3 else 'FAIL'}\n")
    all_ok &= ok3
    page.close()

    # --- Scenario 4: a case that errored before any records were read (e.g. no PDFs found) --
    # primary_group_ready is false, so the action must be "View status", never "Continue
    # reviewing" (there's nothing to review yet). ---
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    mock_jobs(page, [{
        "job_id": "fake-job-2",
        "folder": "/fake/empty-folder",
        "plaintiff_name": "No Docs Case",
        "defendant_names": [],
        "dol": None,
        "status": "error",
        "started_at": 1784864337.0,
        "finished_at": 1784864338.0,
        "total_documents": 0,
        "group_count": 0,
        "failed_group_count": 0,
        "primary_group_key": "nodocscase",
        "primary_group_ready": False,
    }])
    page.goto(APP_URL)
    page.wait_for_timeout(400)
    row_text = page.locator(".case-row").first.inner_text()
    print(f"[errored case, nothing to review] row text: {row_text!r}")
    ok4 = "view status" in row_text.lower() and "continue reviewing" not in row_text.lower()
    print(f"-> {'PASS' if ok4 else 'FAIL'}\n")
    all_ok &= ok4
    page.close()

    return all_ok


if __name__ == "__main__":
    sys.exit(main())
