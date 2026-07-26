#!/usr/bin/env python3
"""
Reproduces and fixes a real bug found via live testing on case_smith: a reviewer who opens the
review link the moment a case starts (the normal way to use this app) has their very FIRST poll to
/case/<job_id>/<group_key>/results land before Phase 1-3 (Complaint/NOI detection + document
grouping) finishes creating the group entry in the manifest -- which used to return a hard 404
"Unknown group". The frontend's poll loop (fetchAndRenderCaseResult in app.js) treats ANY `error`
field as fatal and never schedules another poll -- so that single early 404 silently killed the
page's polling FOREVER, even long after the job actually finished. The user's real-world symptom:
no Bates numbers in the export, and "source PDFs no longer on disk" when trying to view a citation
-- both are just what a permanently-frozen, never-updated page looks like.

Two levels of coverage:
1. Direct API check: hitting /case/<job_id>/<group_key>/results immediately after starting a real
   case (before groups are populated) must return `{"ready": false, ...}` (200), never a bare
   `error` field/404 -- and a truly bogus group key on an already-DONE job must still correctly
   404, so the fix doesn't accidentally make every bad link "work" forever.
2. Full frontend check: mocks the results endpoint to return that same "not created yet" shape on
   the first poll, then real final data on the second -- confirms the page actually keeps polling
   and renders once real data arrives, rather than freezing after the first response.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_case_group_not_yet_created.py [--headed]
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from case_upload_helpers import urllib_start_case

APP_URL = "http://127.0.0.1:5051"
BASE = Path(__file__).resolve().parent.parent
CASE_FOLDER = BASE / "sample_data" / "case_000_pdfs"  # small/fast is fine -- this race doesn't need a big case


def start_case(plaintiff_name: str) -> str:
    return urllib_start_case(APP_URL, plaintiff_name, CASE_FOLDER)


def get_json(url: str):
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def main():
    headed = "--headed" in sys.argv
    if not CASE_FOLDER.is_dir():
        print(f"FAIL: {CASE_FOLDER} does not exist on this machine — can't run this test")
        return 1

    all_ok = True

    # Uses a group key that will NEVER be a real group regardless of timing (not derived from the
    # plaintiff name), so this specifically isolates "does the response shape depend on whether the
    # job is done yet" without any race against how fast the real primary group gets created.
    job_id = start_case("Race Condition Test Plaintiff")
    BOGUS_GROUP = "this_group_will_never_be_real_xyz"

    # --- Check 1: a poll made the instant a case starts (job not done yet) must not look like a
    # fatal error, even for a group that doesn't exist -- because at THIS point, it's ambiguous
    # whether it just hasn't been created yet, and treating that as fatal is exactly the bug. ---
    status_code, data = get_json(f"{APP_URL}/case/{job_id}/{BOGUS_GROUP}/results")
    print(f"immediate poll (job not done yet) for a nonexistent group: HTTP {status_code}, body={data}")
    ok1 = status_code == 200 and "error" not in data and data.get("ready") is False
    print(f"-> {'PASS' if ok1 else 'FAIL'} (expected 200, ready:false, no error field)\n")
    all_ok &= ok1

    # --- Check 2: once the job reaches a terminal state, that SAME bogus group must correctly
    # 404 -- the fix must not turn every bad link into an infinite "still loading". ---
    print("waiting for that job to finish, to test the genuinely-unknown-group case on a done job...")
    import time
    start = time.time()
    manifest = {}
    while time.time() - start < 120:
        _, manifest = get_json(f"{APP_URL}/case/status/{job_id}")
        if manifest.get("status") == "done":
            break
        time.sleep(3)
    else:
        print("FAIL: job never finished within 120s — can't test the done-job 404 case")
        return 1

    status_code, data = get_json(f"{APP_URL}/case/{job_id}/{BOGUS_GROUP}/results")
    print(f"poll for the same bogus group on a DONE job: HTTP {status_code}, body={data}")
    ok2 = status_code == 404 and data.get("error") == "Unknown group"
    print(f"-> {'PASS' if ok2 else 'FAIL'} (must still hard-404 once the job is actually done)\n")
    all_ok &= ok2

    # --- Check 3: full frontend behavior -- the page must keep polling and eventually render once
    # real data replaces the initial "not created yet" response, not freeze forever. ---
    real_group_key = next(iter(manifest.get("groups", {})), None)
    _, real_final = get_json(f"{APP_URL}/case/{job_id}/{real_group_key}/results")

    call_count = {"n": 0}

    def handler(route):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Exactly the old-404-triggering moment, now fixed to look like this instead.
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "ready": False, "status": "scanning", "progress_text": "Looking for the Complaint/Notice of Intent…", "case": None,
            }))
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(real_final))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            console_errors = []
            page.on("pageerror", lambda e: console_errors.append(f"[PAGEERROR] {e}"))
            page.on("console", lambda m: console_errors.append(f"[console.error] {m.text}") if m.type == "error" else None)
            page.route("**/case/*/*/results", handler)

            page.goto(f"{APP_URL}/review?case=fakejob&group=fakegroup")
            page.wait_for_timeout(1000)
            still_waiting = page.locator("#status").is_visible()
            print(f"after 1st poll ('not created yet' response): still showing waiting UI: {still_waiting}, "
                  f"calls so far: {call_count['n']}")

            # Give the 4s polling interval a couple of cycles to fire the 2nd (real) response.
            page.wait_for_timeout(5000)
            findings_rendered = page.locator(".finding").count() > 0
            print(f"after next poll cycle: findings rendered: {findings_rendered}, "
                  f"total polls made: {call_count['n']}")
            ok3 = still_waiting and findings_rendered and call_count["n"] >= 2
            print(f"-> {'PASS' if ok3 else 'FAIL'} (polling must continue past the first response "
                  f"and eventually render real data)\n")
            all_ok &= ok3

            if console_errors:
                print(f"Console errors seen during run ({len(console_errors)}):")
                for e in console_errors[:10]:
                    print(f"  - {e}")
                all_ok = False
            else:
                print("No console errors during run.")
        finally:
            browser.close()

    print()
    print("PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
