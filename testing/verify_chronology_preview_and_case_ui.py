#!/usr/bin/env python3
"""
Covers three related chronology-builder UI changes:

1. "Preview Chronology" button (bottom of the timeline pane) shows exactly what the Word export
   would produce, rendered as HTML directly in the viewer pane (reusing buildExportPayload() — the
   same data /export/docx renders, so the preview can't drift out of sync with the real export).
   Clicking any finding's citation afterward exits preview mode and shows the source PDF again.
2. The single-zip upload form is hidden entirely when in Case Mode (?case=&group=) -- it made no
   sense to show it there.
3. The "Check for new files" control is now on the review page itself (where a reviewer actually
   works), not just the separate /case status page.

Uses the sessionStorage restore trick (see verify_bates_disambiguation.py) so this is deterministic
-- no LLM call needed.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_chronology_preview_and_case_ui.py [--headed]
"""
import json
import sys
import tempfile
import uuid
from pathlib import Path

from fpdf import FPDF
from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:5051"
PORT = 5051
SESSIONS_DIR = Path(tempfile.gettempdir()) / f"lawfirmagent_sessions_{PORT}"


def make_dummy_pdf(session_id: str, filename: str):
    """A real, minimal PDF backing the fake session data below — without this, clicking a
    citation would 404 (no real file exists for the fake source_file), which is a test-fixture
    gap, not an app bug, but would still pollute the console-error check this test also runs."""
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.write(6, "Right knee arthroscopy performed without complication.\n")
    pdf.write(6, "Patient discharged in stable condition.\n")
    pdf.output(str(session_dir / filename))
    return session_dir


def make_fake_result(session_id: str, with_case_meta: bool = False):
    result = {
        "session_id": session_id,
        "ocr_files": [],
        "record_source_labels": {"record.pdf": "OpReport"},
        "warnings": [],
        "stats": {
            "documents_processed": 1, "total_pages": 1, "wall_time_seconds": 0,
            "tokens_per_second": None, "model": "test-fixture", "detail_level": "standard",
        },
        "findings": {
            "timeline": [
                {
                    "date": "01/05/2026", "text": "Right knee arthroscopy performed without complication.",
                    "source_file": "record.pdf", "quote": "Right knee arthroscopy performed without complication.",
                    "record_type": "Operative Report", "author": "Dr. A. Test",
                    "at_issue": True, "bates": "MED000001",
                },
                {
                    "date": "01/10/2026", "text": "Patient discharged in stable condition.",
                    "source_file": "record.pdf", "quote": None,
                    "record_type": "Discharge Summary", "author": "Dr. A. Test",
                    "at_issue": False, "bates": "MED000002",
                },
            ],
            "potential_issues": [], "discrepancies": [],
            "key_facts": {},
            "patient_demographics": {"dob": "01/01/1980", "past_medical_history": "Hypertension"},
            "summary": "Patient underwent knee surgery and recovered without complication.",
        },
    }
    if with_case_meta:
        result["case"] = {
            "plaintiff_name": "Preview Test Plaintiff",
            "defendant_names": ["Dr. Test Defendant"],
            "dol": "01/05/2026",
            "facts_summary": "Alleged negligence during knee surgery.",
        }
    return result


def main():
    headed = "--headed" in sys.argv
    all_ok = True
    session_dirs_to_clean = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

            # --- Scenario 1: plain /review (no case) -- upload form visible, rescan row hidden. ---
            session_id = uuid.uuid4().hex
            session_dirs_to_clean.append(make_dummy_pdf(session_id, "record.pdf"))
            page.goto(f"{APP_URL}/review")
            page.evaluate(
                "(data) => sessionStorage.setItem('lawfirmagent_last_result', JSON.stringify(data))",
                make_fake_result(session_id),
            )
            page.reload()
            page.wait_for_selector(".finding", timeout=10_000)

            upload_visible = page.locator("#upload-form").is_visible()
            rescan_visible = page.locator("#case-rescan-row").is_visible()
            print(f"[plain /review] upload form visible: {upload_visible}, rescan row visible: {rescan_visible}")
            ok1 = upload_visible and not rescan_visible
            print(f"-> {'PASS' if ok1 else 'FAIL'}\n")
            all_ok &= ok1

            # --- Approve both findings, then preview. ---
            findings = page.locator(".finding")
            for i in range(findings.count()):
                findings.nth(i).click()
                page.wait_for_timeout(150)
                page.keyboard.press("Escape")
                page.wait_for_timeout(100)
                page.locator("#approve-btn").click()
                page.wait_for_timeout(150)

            preview_btn = page.locator("#preview-chronology-btn")
            preview_visible = preview_btn.is_visible()
            # Regression guard for a real bug: the button used to live inside .findings-pane,
            # sticky-positioned to that pane's own bottom edge — but the pane's box can extend
            # below the browser's visible viewport once enough header content (notice/stats/
            # review-bar/rescan-row/facts-panel) pushes the split-view down, making a "sticky"
            # child invisible along with it. Confirmed directly against a real, longer chronology.
            # Now lives in the always-visible review-bar instead — assert its actual on-screen
            # position needs no scrolling, not just that CSS considers it "visible".
            btn_box = preview_btn.bounding_box()
            viewport_size = page.viewport_size
            reachable_without_scrolling = btn_box is not None and 0 <= btn_box["y"] <= viewport_size["height"]
            print(f"preview button visible: {preview_visible}, "
                  f"reachable without scrolling: {reachable_without_scrolling} (box y={btn_box['y'] if btn_box else None})")
            assert reachable_without_scrolling, "preview button requires scrolling to reach — the exact bug this test guards against"
            preview_btn.click()
            page.wait_for_timeout(300)

            modal_shown = page.locator("#chronology-preview-modal").is_visible()
            # A full-screen-width modal (not an inline swap in the viewer pane) — see TEST_RESULTS.md:
            # the whole point is seeing the DATE/PAGE/RECORD/SOURCE/DESCRIPTION table without any
            # horizontal scrolling, which the viewer pane (roughly half the window) couldn't fit.
            modal_box = page.locator(".modal-box-wide").bounding_box()
            viewport_width = page.viewport_size["width"]
            modal_is_wide = modal_box is not None and modal_box["width"] >= viewport_width * 0.85
            preview_text = page.locator("#chronology-preview").inner_text()
            print(f"modal shown: {modal_shown}, modal width: {modal_box['width'] if modal_box else None} "
                  f"of viewport {viewport_width} (wide enough: {modal_is_wide})")
            print(f"contains RE: line: {'RE:' in preview_text}")
            print(f"contains DOB: {'01/01/1980' in preview_text}")
            print(f"contains PMHx: {'Hypertension' in preview_text}")
            print(f"contains at-issue finding text: {'Right knee arthroscopy' in preview_text}")
            print(f"contains second finding text: {'discharged in stable condition' in preview_text}")
            print(f"contains summary: {'recovered without complication' in preview_text}")
            print(f"contains Bates in PAGE column: {'MED000001' in preview_text}")

            ok2 = (
                preview_visible and reachable_without_scrolling and modal_shown and modal_is_wide
                and "RE:" in preview_text and "01/01/1980" in preview_text
                and "Hypertension" in preview_text and "Right knee arthroscopy" in preview_text
                and "discharged in stable condition" in preview_text
                and "recovered without complication" in preview_text
                and "MED000001" in preview_text
            )
            print(f"-> {'PASS' if ok2 else 'FAIL'} (wide modal shown with correct, complete content)\n")
            all_ok &= ok2

            # --- The modal blocks interaction with the page underneath until closed -- close it via
            # its own Close button, confirm it's gone, THEN confirm the source-document viewer
            # (untouched underneath the whole time) still works normally. ---
            page.locator("#chronology-preview-close").click()
            page.wait_for_timeout(300)
            modal_hidden_after_close = not page.locator("#chronology-preview-modal").is_visible()
            print(f"modal hidden after clicking Close: {modal_hidden_after_close}")
            ok2b = modal_hidden_after_close
            print(f"-> {'PASS' if ok2b else 'FAIL'}\n")
            all_ok &= ok2b

            citation = page.locator(".finding-citation").first
            if citation.count():
                citation.click()
                page.wait_for_timeout(800)
                highlight_shown = page.locator(".pdf-highlight").count() > 0
                print(f"source PDF/highlight still works normally after closing the preview modal: {highlight_shown}")
                ok3 = highlight_shown
                print(f"-> {'PASS' if ok3 else 'FAIL'}\n")
                all_ok &= ok3
            else:
                print("No citation chip found to test preview-exit against.\n")
                ok3 = False
                all_ok = False

            # --- Scenario 2: Case Mode -- upload form hidden, rescan row visible. ---
            case_session_id = uuid.uuid4().hex
            session_dirs_to_clean.append(make_dummy_pdf(case_session_id, "record.pdf"))
            fake_case_result = make_fake_result(case_session_id, with_case_meta=True)
            case_response = {
                "ready": True,
                "session_id": fake_case_result["session_id"],
                "findings": fake_case_result["findings"],
                "stats": fake_case_result["stats"],
                "warnings": [], "ocr_files": [],
                "status": "done", "progress_text": None,
                "case": fake_case_result["case"],
                "record_source_labels": fake_case_result["record_source_labels"],
                "review_state": {}, "added_facts": [],
                "rescan_status": None, "rescan_message": None,
            }
            page.route("**/case/fakejob/fakegroup/results", lambda route: route.fulfill(
                status=200, content_type="application/json", body=json.dumps(case_response),
            ))
            page.goto(f"{APP_URL}/review?case=fakejob&group=fakegroup")
            page.wait_for_selector(".finding", timeout=10_000)
            page.wait_for_timeout(500)

            upload_visible_case = page.locator("#upload-form").is_visible()
            rescan_visible_case = page.locator("#case-rescan-row").is_visible()
            rescan_btn_text = page.locator("#review-rescan-btn").inner_text() if rescan_visible_case else "(not shown)"
            print(f"[case mode] upload form visible: {upload_visible_case}, "
                  f"rescan row visible: {rescan_visible_case}, rescan btn text: {rescan_btn_text!r}")
            ok4 = (not upload_visible_case) and rescan_visible_case
            print(f"-> {'PASS' if ok4 else 'FAIL'}\n")
            all_ok &= ok4

            if console_errors:
                print(f"Console errors seen during run ({len(console_errors)}):")
                for e in console_errors[:10]:
                    print(f"  - {e}")
                all_ok = False
            else:
                print("No console errors during run.")
        finally:
            browser.close()

    import shutil
    for d in session_dirs_to_clean:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print("PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
