#!/usr/bin/env python3
"""
Confirms the "export with unreviewed findings" warning is a styled in-app modal, not the browser's
native confirm() dialog — a plain OS-chrome dialog looked out of place next to the rest of this
app's custom UI. Uses the sessionStorage restore trick (see verify_bates_disambiguation.py) to seed
several unreviewed findings deterministically, no LLM call needed.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_export_confirm_modal.py [--headed]
"""
import sys
import uuid

from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:5051"


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
            "timeline": [
                {
                    "date": f"01/0{i}/2026", "text": f"Finding {i}", "source_file": "record.pdf",
                    "quote": None, "record_type": "Note", "author": "Dr. Test",
                    "at_issue": False, "bates": None,
                }
                for i in range(1, 4)
            ],
            "potential_issues": [], "discrepancies": [], "key_facts": {},
        },
    }


def main():
    headed = "--headed" in sys.argv
    session_id = uuid.uuid4().hex

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))
            page.on("dialog", lambda d: (_ for _ in ()).throw(
                AssertionError(f"native browser dialog appeared: {d.message!r} — should be a styled modal")
            ))

            page.goto(f"{APP_URL}/review")
            page.evaluate(
                "(data) => sessionStorage.setItem('lawfirmagent_last_result', JSON.stringify(data))",
                make_fake_result(session_id),
            )
            page.reload()
            page.wait_for_selector(".finding", timeout=10_000)

            # Approve exactly one of the three findings, leaving 2 unreviewed -> export should warn.
            page.locator(".finding").first.click()
            page.click("#approve-btn")
            page.wait_for_timeout(200)

            all_ok = True

            # --- Click export: styled modal should appear (not a native dialog -- the `dialog`
            # handler above would raise if one did). ---
            page.click("#export-btn")
            page.wait_for_timeout(300)
            modal_visible = page.locator("#export-confirm-modal").is_visible()
            message = page.locator("#export-confirm-message").inner_text()
            print(f"styled modal shown on export with unreviewed findings: {modal_visible}")
            print(f"message: {message!r}")
            modal_ok = modal_visible and "2 of 3" in message
            print(f"-> {'PASS' if modal_ok else 'FAIL'} (expected visible modal mentioning '2 of 3')\n")
            all_ok &= modal_ok

            # --- Cancel: modal closes, no export request fires. ---
            export_requests = []
            page.on("request", lambda r: export_requests.append(r.url) if "/export/docx" in r.url else None)
            page.click("#export-confirm-cancel")
            page.wait_for_timeout(300)
            cancel_ok = not page.locator("#export-confirm-modal").is_visible() and not export_requests
            print(f"cancel closes modal, no export request sent: {cancel_ok} -> {'PASS' if cancel_ok else 'FAIL'}\n")
            all_ok &= cancel_ok

            # --- Export Anyway: modal closes and the export request actually fires. ---
            page.click("#export-btn")
            page.wait_for_timeout(300)
            with page.expect_request("**/export/docx", timeout=5000) as req_info:
                page.click("#export-confirm-proceed")
            fired = req_info.value is not None
            page.wait_for_timeout(300)
            proceed_ok = fired and not page.locator("#export-confirm-modal").is_visible()
            print(f"'Export Anyway' closes modal and fires the export request: {proceed_ok} "
                  f"-> {'PASS' if proceed_ok else 'FAIL'}\n")
            all_ok &= proceed_ok

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
