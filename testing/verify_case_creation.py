#!/usr/bin/env python3
"""Drives Case Mode end-to-end against the two fixtures built by
scripts/make_case_test_folders.py:

- case_smith/: has a Complaint/NOI in pleadings/ — confirms it's auto-detected, defendant name(s)/
  DOL/facts are extracted and shown on the case status page, the folder's OTHER subfolders
  (correspondence/depositions/etc., not just records/) get ingested, and the resulting chronology
  shows record_type/author (bold header) and at_issue flagging on findings.
- case_nodefendant/: has no complaint/NOI anywhere — confirms the app proceeds anyway and surfaces
  a clear warning instead of failing the case.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from case_upload_helpers import start_case as _start_case

BASE = Path(__file__).resolve().parent.parent
APP_URL = "http://127.0.0.1:5051"
CASE_SMITH = BASE / "sample_data" / "case_smith"
CASE_NODEFENDANT = BASE / "sample_data" / "case_nodefendant"


def start_case(page, plaintiff_name, folder, priority_hint=""):
    return _start_case(page, APP_URL, plaintiff_name, folder, priority_hint=priority_hint)


def wait_for_group_done(page, job_id, group_key, timeout_s=600):
    deadline = time.time() + timeout_s
    last_manifest = None
    while time.time() < deadline:
        manifest = page.request.get(f"{APP_URL}/case/status/{job_id}").json()
        last_manifest = manifest
        group = manifest.get("groups", {}).get(group_key)
        if group and group.get("status") in ("done", "failed"):
            return manifest
        time.sleep(3)
    raise TimeoutError(f"case job never finished group {group_key}: {last_manifest}")


def run_checks(browser) -> bool:
    ok = True
    page = browser.new_page(viewport={"width": 1500, "height": 950})
    console_errors = []
    page.on("pageerror", lambda e: console_errors.append(f"[PAGEERROR] {e}"))
    page.on("console", lambda m: console_errors.append(f"[console.error] {m.text}") if m.type == "error" else None)

    # --- case_smith: complaint present ---
    job_id = start_case(page, "Jane Smith", CASE_SMITH, priority_hint="records")
    manifest = wait_for_group_done(page, job_id, "janesmith", timeout_s=900)

    print("defendant_names:", manifest.get("defendant_names"))
    print("dol:", manifest.get("dol"))
    print("facts_summary:", (manifest.get("facts_summary") or "")[:80])
    print("complaint_source_file:", manifest.get("complaint_source_file"))
    print("complaint_warning:", manifest.get("complaint_warning"))

    complaint_ok = (
        bool(manifest.get("defendant_names"))
        and manifest.get("dol")
        and manifest.get("complaint_source_file") == "complaint.pdf"
        and not manifest.get("complaint_warning")
    )
    print("complaint auto-detection + extraction:", "PASS" if complaint_ok else "FAIL")
    ok &= complaint_ok

    group = manifest["groups"]["janesmith"]
    if group["status"] != "done":
        print(f"FAIL: janesmith group ended in status {group['status']}: {group.get('error')}")
        ok = False
    else:
        # Open the actual results page and check record_type/author/at_issue rendering.
        page.goto(f"{APP_URL}/review?case={job_id}&group=janesmith")
        page.wait_for_selector("#results", state="visible", timeout=60_000)
        page.wait_for_timeout(1000)

        finding_count = page.locator(".finding").count()
        header_count = page.locator(".finding-record-header").count()
        at_issue_count = page.locator(".finding.at-issue").count()
        print(f"findings: {finding_count}, with record-type/author header: {header_count}, at-issue: {at_issue_count}")
        display_ok = finding_count > 0 and header_count > 0
        print("record_type/author display:", "PASS" if display_ok else "FAIL")
        ok &= display_ok
        # at_issue is model-judged, not guaranteed on every run — just confirm the mechanism
        # renders correctly when the model does flag something, not that it always does.
        if at_issue_count:
            print("at_issue badge rendering: PASS (at least one entry flagged)")
        else:
            print("at_issue badge rendering: no entries flagged this run (model judgment call, not a failure)")

    # --- case_nodefendant: no complaint anywhere ---
    job_id2 = start_case(page, "Robert Nguyen", CASE_NODEFENDANT)
    manifest2 = wait_for_group_done(page, job_id2, "robertnguyen", timeout_s=1200)
    warning_ok = bool(manifest2.get("complaint_warning")) and not manifest2.get("defendant_names")
    print("complaint_warning (no complaint present):", manifest2.get("complaint_warning"))
    print("no-complaint fallback:", "PASS" if warning_ok else "FAIL")
    ok &= warning_ok

    group2 = manifest2["groups"]["robertnguyen"]
    proceeded_ok = group2["status"] == "done"
    print("case proceeded despite no complaint:", "PASS" if proceeded_ok else f"FAIL ({group2.get('status')})")
    ok &= proceeded_ok

    print("console errors:", console_errors)
    ok &= not console_errors
    return ok


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ok = run_checks(browser)
        finally:
            # Always close the browser, even on failure/timeout — an uncaught exception here
            # previously left a headless Chromium process running with a case job it had started
            # still in flight server-side, silently occupying Ollama's one concurrency slot and
            # starving whatever test ran next.
            browser.close()

    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
