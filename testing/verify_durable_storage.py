#!/usr/bin/env python3
"""
Confirms Case Mode data is genuinely durable — the actual point of the SQLite/app-data-dir switch
(see db.py): a case's chronology, review state, and source PDFs must survive a server restart and
be recoverable from a completely fresh browser (no shared sessionStorage), not just live for as
long as one browser tab/process happens to stay open.

Spins up its OWN dedicated Flask server subprocess on a throwaway port, with LAWFIRMAGENT_DATA_DIR
pointed at a throwaway directory (never touches a real user's app-data dir), so this test can freely
kill and restart that process without disturbing the shared port-5051 test server other tests use.

Usage: testing/.venv/bin/python testing/verify_durable_storage.py [--headed]
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

from case_upload_helpers import start_case

BASE = Path(__file__).resolve().parent.parent
WEBAPP_DIR = BASE / "webapp"
CASE_FOLDER = BASE / "sample_data" / "case_000_pdfs"  # small/fast — this test is about persistence, not scale
PORT = 5098
APP_URL = f"http://127.0.0.1:{PORT}"


def _install_test_license(data_dir: Path) -> None:
    """A throwaway data dir has no license.token yet, and every non-exempt route 402s without one
    (see app.py's _enforce_license) — issue a real one so this test can actually drive Case Mode."""
    token = subprocess.check_output(
        [str(WEBAPP_DIR / ".venv" / "bin" / "python"), str(BASE / "scripts" / "license_tool.py"),
         "issue", "--tier", "lifetime", "--customer", "durable-storage-test"],
        text=True,
    ).strip().splitlines()[-1]
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "license.token").write_text(token)


def start_server(data_dir: Path) -> subprocess.Popen:
    proc = subprocess.Popen(
        [str(WEBAPP_DIR / ".venv" / "bin" / "python"), "app.py"],
        cwd=str(WEBAPP_DIR),
        env={**os.environ, "LAWFIRMAGENT_PORT": str(PORT), "LAWFIRMAGENT_DATA_DIR": str(data_dir)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    import urllib.request
    while time.time() < deadline:
        try:
            urllib.request.urlopen(APP_URL, timeout=2)
            _install_test_license(data_dir)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("test server never became ready")


def stop_server(proc: subprocess.Popen):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def check_default_app_data_dir_not_tempdir() -> bool:
    """Unit-level check, independent of this test's own (deliberately temp-based, for easy
    cleanup) throwaway data dir override: with LAWFIRMAGENT_DATA_DIR unset, db.get_app_data_dir()
    must resolve to a real per-OS application-data location, not tempfile.gettempdir()."""
    sys.path.insert(0, str(WEBAPP_DIR))
    os.environ.pop("LAWFIRMAGENT_DATA_DIR", None)
    import db as db_module
    default_dir = db_module.get_app_data_dir()
    ok = str(default_dir) != tempfile.gettempdir() and not str(default_dir).startswith(tempfile.gettempdir())
    print(f"default app-data dir (no override): {default_dir}")
    print(f"-> {'PASS' if ok else 'FAIL'} (must not default to tempfile.gettempdir())\n")
    return ok


def main():
    headed = "--headed" in sys.argv
    all_ok = check_default_app_data_dir_not_tempdir()

    data_dir = Path(tempfile.gettempdir()) / f"lfa_durable_test_{uuid.uuid4().hex[:8]}"

    proc = start_server(data_dir)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                job_id = start_case(page, APP_URL, "Durable Storage Test Plaintiff", CASE_FOLDER)
                print(f"started case {job_id}")

                deadline = time.time() + 300
                manifest = None
                while time.time() < deadline:
                    manifest = page.request.get(f"{APP_URL}/case/status/{job_id}").json()
                    if manifest.get("status") == "done":
                        break
                    time.sleep(3)
                else:
                    print("FAIL: case never finished")
                    return 1

                group_key = next(iter(manifest["groups"]))
                print(f"case done, group_key={group_key}")

                # --- Check 1: the case's own data actually landed under the configured app-data
                # dir (LAWFIRMAGENT_DATA_DIR here, for test isolation) rather than somewhere else
                # entirely -- the "not tempfile.gettempdir() by default" property itself is checked
                # separately above, since this test's own throwaway fixture dir is deliberately
                # temp-based for easy cleanup. ---
                db_path = data_dir / "lawfirmagent.db"
                session_dir = data_dir / "case_sessions" / f"case_{job_id}_{group_key}"
                db_exists = db_path.is_file()
                session_exists = session_dir.is_dir() and any(session_dir.glob("*.pdf"))
                print(f"db exists at {db_path}: {db_exists}")
                print(f"session PDFs exist at {session_dir}: {session_exists}")
                ok1 = db_exists and session_exists
                print(f"-> {'PASS' if ok1 else 'FAIL'}\n")
                all_ok &= ok1

                # --- Set up review state to prove durability of: approve, edit, added fact, summary edit ---
                page.goto(f"{APP_URL}/review?case={job_id}&group={group_key}")
                page.wait_for_selector(".finding", timeout=15_000)
                page.wait_for_timeout(1500)  # let the durable review_state/added_facts pre-seed logic settle

                first_finding = page.locator(".finding").first
                first_finding.click()
                page.wait_for_timeout(200)
                page.keyboard.press("Escape")  # back out of click-opens-edit-mode
                page.wait_for_timeout(100)
                page.locator("#approve-btn").click()
                page.wait_for_timeout(300)

                # Also durably edit the summary, if present.
                if page.locator(".summary-box").count():
                    page.locator(".summary-box").click()
                    page.wait_for_timeout(200)
                    page.locator("textarea.summary-edit-textarea").fill("DURABLY EDITED SUMMARY TEXT")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)

                page.wait_for_timeout(500)  # let fire-and-forget durability POSTs land
            finally:
                browser.close()

        # --- Check 2: restart the server process entirely, confirm data survives ---
        print("restarting the test server process...")
        stop_server(proc)
        proc = start_server(data_dir)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                jobs = page.request.get(f"{APP_URL}/case/jobs").json()
                job_ids = [j["job_id"] for j in jobs]
                print(f"jobs visible after restart: {job_ids}")
                ok2 = job_id in job_ids
                print(f"-> {'PASS' if ok2 else 'FAIL'} (case still listed after server restart)\n")
                all_ok &= ok2

                results = page.request.get(f"{APP_URL}/case/{job_id}/{group_key}/results").json()
                findings_present = bool(results.get("findings", {}).get("timeline")) or bool(results.get("ready"))
                print(f"results still fetchable after restart: {results.get('ready')}")
                ok3 = results.get("ready") is True
                print(f"-> {'PASS' if ok3 else 'FAIL'}\n")
                all_ok &= ok3

                # --- Check 3: a BRAND NEW browser context (no shared sessionStorage) sees the
                # durably-saved review state and highlighting still works. This is the actual
                # "come back a month later, different session" proof. ---
                fresh_context = browser.new_context()
                fresh_page = fresh_context.new_page()
                console_errors = []
                fresh_page.on("pageerror", lambda e: console_errors.append(f"[PAGEERROR] {e}"))
                fresh_page.on("console", lambda m: console_errors.append(f"[console.error] {m.text}") if m.type == "error" else None)

                fresh_page.goto(f"{APP_URL}/review?case={job_id}&group={group_key}")
                fresh_page.wait_for_selector(".finding", timeout=15_000)
                fresh_page.wait_for_timeout(1000)

                approved_count = fresh_page.locator(".finding.status-approved").count()
                print(f"approved findings visible in a brand-new browser context: {approved_count}")
                ok4 = approved_count >= 1
                print(f"-> {'PASS' if ok4 else 'FAIL'} (review state durably restored, not just from sessionStorage)\n")
                all_ok &= ok4

                if fresh_page.locator(".summary-box").count():
                    summary_text = fresh_page.locator(".summary-box").inner_text()
                    print(f"summary text in fresh context: {summary_text!r}")
                    ok5 = "DURABLY EDITED SUMMARY TEXT" in summary_text
                    print(f"-> {'PASS' if ok5 else 'FAIL'} (summary edit durably restored)\n")
                    all_ok &= ok5

                # Highlighting still works from a completely fresh context/session too.
                citation = fresh_page.locator(".finding-citation").first
                if citation.count():
                    citation.click()
                    fresh_page.wait_for_timeout(1200)
                    highlight_count = fresh_page.locator(".pdf-highlight").count()
                    viewer_title = fresh_page.locator("#viewer-title").inner_text()
                    print(f"highlight boxes in fresh context: {highlight_count}, viewer title: {viewer_title!r}")
                    ok6 = highlight_count > 0 and "expired" not in viewer_title.lower()
                    print(f"-> {'PASS' if ok6 else 'FAIL'} (source PDF still loads/highlights after restart)\n")
                    all_ok &= ok6

                if console_errors:
                    print(f"Console errors in fresh context: {console_errors[:10]}")
                    all_ok = False
                else:
                    print("No console errors in fresh context.")

                fresh_context.close()
            finally:
                browser.close()
    finally:
        stop_server(proc)
        shutil.rmtree(data_dir, ignore_errors=True)

    print()
    print("PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
