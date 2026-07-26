#!/usr/bin/env python3
"""
Confirms incremental reprocessing (POST /case/<job_id>/rescan, see _run_case_rescan in app.py):
after a case is done, adding a new file to its folder and triggering a rescan reprocesses ONLY that
new file (not the whole case again), merges its findings into the existing chronology, leaves
previously-reviewed findings' ids/status untouched, and a second no-op rescan correctly reports "no
new files" without calling the model again.

Runs against a TEMP COPY of a small fixture folder (case_000_pdfs) so this test can freely add a
new file without touching a checked-in fixture.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_incremental_reprocessing.py [--headed]
"""
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

from fpdf import FPDF
from playwright.sync_api import sync_playwright

from case_upload_helpers import rescan_case
from case_upload_helpers import start_case as _start_case

BASE = Path(__file__).resolve().parent.parent
APP_URL = "http://127.0.0.1:5051"
SOURCE_FOLDER = BASE / "sample_data" / "case_000_pdfs"

NEW_RECORD_TEXT = """### Record 2 - Test Clinic - Follow-up Visit
**Date of Service:** 06/15/2026
**Provider:** Dr. A. Test
Chief complaint: Follow-up for strep throat, now with new right ear pain.
HPI: Patient's sore throat resolved with amoxicillin. Now reports 2 days of right ear pain and
decreased hearing.
Exam: Right tympanic membrane erythematous and bulging. Left ear clear.
Assessment: Acute otitis media, right ear.
Plan: Started on amoxicillin-clavulanate for otitis media. Follow up in 2 weeks.
"""
NEW_RECORD_BATES = "MED000900"


class BatesPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        self.set_x(0)
        self.cell(self.w, 10, NEW_RECORD_BATES, align="C")


def build_new_record(dest: Path):
    pdf = BatesPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in NEW_RECORD_TEXT.split("\n"):
        pdf.write(6, line + "\n")
    pdf.output(str(dest))


def wait_for_job_done(page, job_id, timeout_s=300):
    deadline = time.time() + timeout_s
    manifest = None
    while time.time() < deadline:
        manifest = page.request.get(f"{APP_URL}/case/status/{job_id}").json()
        if manifest.get("status") == "done":
            return manifest
        time.sleep(3)
    raise TimeoutError(f"case never finished: {manifest}")


def wait_for_rescan_done(page, job_id, timeout_s=300):
    deadline = time.time() + timeout_s
    manifest = None
    while time.time() < deadline:
        manifest = page.request.get(f"{APP_URL}/case/status/{job_id}").json()
        if manifest.get("rescan_status") == "done":
            return manifest
        time.sleep(3)
    raise TimeoutError(f"rescan never finished: {manifest}")


def main():
    headed = "--headed" in sys.argv
    test_folder = Path(tempfile.gettempdir()) / f"lfa_incremental_test_{uuid.uuid4().hex[:8]}"
    shutil.copytree(SOURCE_FOLDER, test_folder)
    all_ok = True

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1000})

                job_id = _start_case(page, APP_URL, "Incremental Test Plaintiff", test_folder)
                print(f"started case {job_id} against {test_folder}")
                manifest = wait_for_job_done(page, job_id)
                group_key = next(iter(manifest["groups"]))
                original_finding_ids = {
                    item["finding_id"] for item in manifest["groups"][group_key]["findings"].get("timeline", [])
                }
                print(f"initial run: {len(original_finding_ids)} timeline finding(s), group={group_key}")

                # Approve + edit one finding, so we can later confirm it survives the rescan/merge
                # with the SAME id and status -- the actual regression guard for the merge-ordering
                # requirement (existing findings must be passed first into _merge_incremental_group_result).
                page.goto(f"{APP_URL}/review?case={job_id}&group={group_key}")
                page.wait_for_selector(".finding", timeout=15_000)
                first_finding_id = page.locator(".finding").first.get_attribute("data-id")
                page.locator(".finding").first.click()
                page.wait_for_timeout(200)
                page.keyboard.press("Escape")
                page.wait_for_timeout(100)
                page.locator("#approve-btn").click()
                page.wait_for_timeout(500)
                print(f"approved finding_id={first_finding_id}")

                # --- Rescan with NOTHING new: must correctly report "no new files" and not touch anything.
                # Re-uploads the folder's CURRENT contents (as if the reviewer re-picked it via the
                # native folder picker) rather than a bodyless POST -- there's no server-side path
                # left to silently re-scan on its own (see /case/start's upload-based redesign). ---
                resp = rescan_case(page, APP_URL, job_id, test_folder)
                assert resp.ok, resp.text()
                manifest = wait_for_rescan_done(page, job_id)
                no_op_message = manifest.get("rescan_message")
                print(f"no-op rescan message: {no_op_message!r}")
                ok0 = no_op_message is not None and "no new" in no_op_message.lower()
                print(f"-> {'PASS' if ok0 else 'FAIL'} (no-op rescan correctly found nothing new)\n")
                all_ok &= ok0

                # --- Add a genuinely new file, rescan for real. ---
                build_new_record(test_folder / "record_02.pdf")
                resp = rescan_case(page, APP_URL, job_id, test_folder)
                assert resp.ok, resp.text()
                manifest = wait_for_rescan_done(page, job_id)
                rescan_message = manifest.get("rescan_message")
                print(f"real rescan message: {rescan_message!r}")

                new_findings = manifest["groups"][group_key]["findings"].get("timeline", [])
                new_finding_ids = {item["finding_id"] for item in new_findings}
                added_ids = new_finding_ids - original_finding_ids
                traceable = any(
                    item.get("source_file") == "record_02.pdf" or item.get("bates") == NEW_RECORD_BATES
                    for item in new_findings if item["finding_id"] in added_ids
                )
                print(f"new finding ids added: {len(added_ids)}, traceable to record_02.pdf: {traceable}")
                ok1 = len(added_ids) > 0 and traceable
                print(f"-> {'PASS' if ok1 else 'FAIL'} (new file's findings actually appear)\n")
                all_ok &= ok1

                # --- The previously-approved finding's id must survive unchanged, and still show approved
                # in a completely fresh browser context (durable review state, not just this tab's own). ---
                ids_after = {item["finding_id"] for item in new_findings}
                id_survived = first_finding_id in ids_after
                print(f"previously-approved finding_id survived the merge: {id_survived}")

                fresh_context = browser.new_context()
                fresh_page = fresh_context.new_page()
                fresh_page.goto(f"{APP_URL}/review?case={job_id}&group={group_key}")
                fresh_page.wait_for_selector(".finding", timeout=15_000)
                fresh_page.wait_for_timeout(800)
                still_approved = fresh_page.locator(
                    f'.finding.status-approved[data-id="{first_finding_id}"]'
                ).count() > 0
                print(f"still shows approved in a fresh browser context: {still_approved}")
                fresh_context.close()

                ok2 = id_survived and still_approved
                print(f"-> {'PASS' if ok2 else 'FAIL'}\n")
                all_ok &= ok2

                # --- A second no-op rescan (nothing new since the last real one) must also correctly
                # report nothing new, proving processed_files tracking now includes record_02.pdf too. ---
                resp = rescan_case(page, APP_URL, job_id, test_folder)
                assert resp.ok, resp.text()
                manifest = wait_for_rescan_done(page, job_id)
                second_noop_message = manifest.get("rescan_message")
                print(f"second no-op rescan message: {second_noop_message!r}")
                ok3 = second_noop_message is not None and "no new" in second_noop_message.lower()
                print(f"-> {'PASS' if ok3 else 'FAIL'} (record_02.pdf now correctly tracked as processed)\n")
                all_ok &= ok3

                # --- Rescan attempted with no folder re-selected (no files in the upload) -> clean 400,
                # not a raw exception. There's no more server-side original-folder path that could go
                # missing (see /case/start's upload-based redesign) -- the analogous failure mode now
                # is the reviewer never re-picking a folder at all before the upload fires. ---
                resp = page.request.post(f"{APP_URL}/case/{job_id}/rescan")
                body = resp.json()
                print(f"rescan with no files uploaded: HTTP {resp.status}, body={body}")
                ok4 = resp.status == 400 and "error" in body
                print(f"-> {'PASS' if ok4 else 'FAIL'}\n")
                all_ok &= ok4
            finally:
                browser.close()
    finally:
        shutil.rmtree(test_folder, ignore_errors=True)

    print()
    print("PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
