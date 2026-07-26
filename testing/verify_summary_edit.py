#!/usr/bin/env python3
"""
Confirms the AI-drafted summary box at the bottom of the timeline is click-to-edit, the same way
individual findings are (see verify_edit_feature.py / startEditingFinding in app.js): clicking it
opens an inline textarea pre-filled with the current text, Enter commits, Escape cancels, the edit
persists across a page refresh (same sessionStorage pattern as everything else reviewed here), and
the edited text -- not the original -- is what actually ends up in the exported chronology.

Uses the sessionStorage restore trick (see verify_bates_disambiguation.py) so this is fully
deterministic -- no LLM call needed.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_summary_edit.py [--headed]
"""
import sys
import uuid
from pathlib import Path

from docx import Document
from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:5051"
ORIGINAL_SUMMARY = "Patient was seen twice for knee pain and ultimately underwent arthroscopy."
EDITED_SUMMARY = "EDITED SUMMARY: patient's knee pain was misdiagnosed for six weeks before arthroscopy."


def make_fake_result(session_id: str):
    return {
        "session_id": session_id,
        "ocr_files": [],
        "record_source_labels": {"record.pdf": "TestRecord"},
        "warnings": [],
        "stats": {
            "documents_processed": 1, "total_pages": 1, "wall_time_seconds": 0,
            "tokens_per_second": None, "model": "test-fixture", "detail_level": "standard",
        },
        "findings": {
            "timeline": [{
                "date": "01/01/2026", "text": "Patient seen for knee pain.",
                "source_file": "record.pdf", "quote": None, "record_type": "Note",
                "author": "Dr. Test", "at_issue": False, "bates": None,
            }],
            "potential_issues": [], "discrepancies": [], "key_facts": {},
            "summary": ORIGINAL_SUMMARY,
        },
    }


def main():
    headed = "--headed" in sys.argv
    session_id = uuid.uuid4().hex
    all_ok = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

            page.goto(f"{APP_URL}/review")
            page.evaluate(
                "(data) => sessionStorage.setItem('lawfirmagent_last_result', JSON.stringify(data))",
                make_fake_result(session_id),
            )
            page.reload()
            page.wait_for_selector(".summary-box", timeout=10_000)

            original_shown = page.locator(".summary-box").inner_text()
            print(f"initial summary text: {original_shown!r}")
            ok0 = original_shown == ORIGINAL_SUMMARY
            print(f"-> {'PASS' if ok0 else 'FAIL'} (matches server-provided summary)\n")
            all_ok &= ok0

            # --- Click opens an inline editor pre-filled with the current text. ---
            page.locator(".summary-box").click()
            page.wait_for_timeout(200)
            textarea = page.locator("textarea.summary-edit-textarea")
            opened = textarea.count() > 0
            prefill_ok = opened and textarea.input_value() == ORIGINAL_SUMMARY
            print(f"clicking opened an editor: {opened}, pre-filled with original text: {prefill_ok}")
            print(f"-> {'PASS' if prefill_ok else 'FAIL'}\n")
            all_ok &= prefill_ok

            # --- Escape cancels without changing anything. ---
            textarea.fill("this should be discarded")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            after_escape = page.locator(".summary-box").inner_text()
            escape_ok = after_escape == ORIGINAL_SUMMARY
            print(f"after Escape, summary is still original: {escape_ok} ({after_escape!r})")
            print(f"-> {'PASS' if escape_ok else 'FAIL'}\n")
            all_ok &= escape_ok

            # --- Click again, edit for real, Enter commits. ---
            page.locator(".summary-box").click()
            page.wait_for_timeout(200)
            page.locator("textarea.summary-edit-textarea").fill(EDITED_SUMMARY)
            page.keyboard.press("Enter")
            page.wait_for_timeout(200)
            after_commit = page.locator(".summary-box").inner_text()
            commit_ok = after_commit == EDITED_SUMMARY
            print(f"after Enter, summary shows the edited text: {commit_ok} ({after_commit!r})")
            print(f"-> {'PASS' if commit_ok else 'FAIL'}\n")
            all_ok &= commit_ok

            # --- Survives a page refresh, same as review status/finding edits/added facts. ---
            page.reload()
            page.wait_for_selector(".summary-box", timeout=10_000)
            after_reload = page.locator(".summary-box").inner_text()
            reload_ok = after_reload == EDITED_SUMMARY
            print(f"edited summary survives a page refresh: {reload_ok} ({after_reload!r})")
            print(f"-> {'PASS' if reload_ok else 'FAIL'}\n")
            all_ok &= reload_ok

            # --- The edited text (not the original) is what actually exports. ---
            # Export is disabled until at least one finding is approved -- approve the one finding
            # this fixture has so the button is clickable.
            page.locator(".finding").first.click()
            page.wait_for_timeout(200)
            page.keyboard.press("Escape")  # this fixture's finding has no quote, but clicking it
            page.wait_for_timeout(100)     # still opens the inline editor (see makeFindingEl) -- back out of it
            page.locator("#approve-btn").click()
            page.wait_for_timeout(200)

            with page.expect_download() as dl_info:
                page.locator("#export-btn").click()
                page.wait_for_timeout(300)
                proceed_btn = page.locator("#export-confirm-proceed")
                if proceed_btn.is_visible():
                    proceed_btn.click()
            download = dl_info.value
            export_path = Path("/tmp/lfa_summary_edit_test.docx")
            download.save_as(str(export_path))
            doc = Document(export_path)
            export_text = "\n".join(p.text for p in doc.paragraphs)
            export_ok = EDITED_SUMMARY in export_text and ORIGINAL_SUMMARY not in export_text
            print(f"exported document contains edited summary (not original): {export_ok}")
            print(f"-> {'PASS' if export_ok else 'FAIL'}\n")
            all_ok &= export_ok

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
