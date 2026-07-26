#!/usr/bin/env python3
"""
Deliberate "trap" test for the highlight-disambiguation logic in showFinding/findQuoteInDoc
(see static/app.js). Builds a 2-page PDF where the IDENTICAL sentence appears on both pages,
each stamped with a different Bates number, then hand-crafts findings (via the sessionStorage
restore trick — no LLM call needed, so this is fully deterministic) that cite each page in turn.

This proves the app picks the page whose Bates stamp actually matches the finding's citation,
not just the first textual match — the exact failure mode the user was worried about
("I really cannot afford to have any instances where ... we are showing the wrong document").

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_bates_disambiguation.py [--headed]
"""
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

from fpdf import FPDF
from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:5051"
PORT = 5051
SESSIONS_DIR = Path(tempfile.gettempdir()) / f"lawfirmagent_sessions_{PORT}"
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"

TRAP_SENTENCE = "Patient reports severe headache and blurred vision following the procedure."
PAGE1_BATES = "MED000010"
PAGE2_BATES = "MED000099"
NONEXISTENT_BATES = "MED000005"  # cited by a finding but stamped on neither page


class BatesPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        bates = PAGE1_BATES if self.page_no() == 1 else PAGE2_BATES
        self.set_x(0)
        self.cell(self.w, 10, bates, align="C")


def build_trap_pdf(dest: Path):
    pdf = BatesPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.write(6, "PROGRESS NOTE - VISIT 1\nDate: 01/05/2026\nAuthor: Dr. A. Nguyen\n\n")
    pdf.write(6, f"{TRAP_SENTENCE}\n")
    pdf.write(6, "Plan: supportive care, follow up in one week.\n")

    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.write(6, "PROGRESS NOTE - VISIT 2\nDate: 01/12/2026\nAuthor: Dr. A. Nguyen\n\n")
    pdf.write(6, f"{TRAP_SENTENCE}\n")
    pdf.write(6, "Plan: symptoms persist, ordering CT head without contrast.\n")
    pdf.output(str(dest))


def make_fake_result(session_id: str, filename: str, cited_bates: str, finding_id: str):
    return {
        "session_id": session_id,
        "ocr_files": [],
        "record_source_labels": {filename: "TrapRecord"},
        "warnings": [],
        "stats": {
            "documents_processed": 1, "total_pages": 2, "wall_time_seconds": 0,
            "tokens_per_second": None, "model": "test-fixture", "detail_level": "standard",
        },
        "findings": {
            "timeline": [
                {
                    "date": "01/05/2026" if cited_bates == PAGE1_BATES else "01/12/2026",
                    "text": f"[{finding_id}] Patient reports headache and blurred vision.",
                    "source_file": filename,
                    "quote": TRAP_SENTENCE,
                    "record_type": "Progress Note",
                    "author": "Dr. A. Nguyen",
                    "at_issue": False,
                    "bates": cited_bates,
                }
            ],
            "potential_issues": [],
            "discrepancies": [],
            "key_facts": {},
        },
    }


def run_case(page, session_id: str, filename: str, cited_bates: str, label: str):
    """Restores a fake result citing `cited_bates` for the trap sentence, clicks the finding's
    citation, and returns the observed (page_num, banner_class, banner_text)."""
    fake = make_fake_result(session_id, filename, cited_bates, label)
    page.goto(f"{APP_URL}/review")
    page.evaluate(
        "(data) => sessionStorage.setItem('lawfirmagent_last_result', JSON.stringify(data))",
        fake,
    )
    page.reload()
    page.wait_for_selector(".finding", timeout=10_000)
    citation = page.locator(".finding-citation").first
    citation.click()
    page.wait_for_timeout(1000)

    page_info = page.locator("#viewer-page-info").inner_text()
    banner = page.locator("#viewer-bates-check")
    banner_class = banner.get_attribute("class") or ""
    banner_text = banner.inner_text() if banner.count() else ""
    highlight_count = page.locator(".pdf-highlight").count()

    screenshot_path = SCREENSHOT_DIR / f"bates_trap_{label}.png"
    page.locator(".viewer-pane").screenshot(path=str(screenshot_path))

    return page_info, banner_class, banner_text, highlight_count


def main():
    headed = "--headed" in sys.argv
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    session_id = uuid.uuid4().hex
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    filename = "trap_record.pdf"
    pdf_path = session_dir / filename
    try:
        build_trap_pdf(pdf_path)
        print(f"Built trap PDF at {pdf_path}")
        print(f"  page 1 bates: {PAGE1_BATES} | page 2 bates: {PAGE2_BATES}")
        print(f"  identical sentence on both pages: {TRAP_SENTENCE!r}\n")

        all_ok = True
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                console_errors = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

                # Case 1: finding cites page 2's Bates number -> must land on page 2, show "match".
                page_info, cls, text, hl = run_case(page, session_id, filename, PAGE2_BATES, "cites_page2")
                print(f"[cites page 2 bates] viewer shows: {page_info!r}")
                print(f"  banner class={cls!r}")
                print(f"  banner text={text!r}")
                print(f"  highlight boxes drawn: {hl}")
                ok1 = "Page 2" in page_info and "match" in cls and "mismatch" not in cls
                print(f"  -> {'PASS' if ok1 else 'FAIL'} (expected page 2 + match banner)\n")
                all_ok &= ok1

                # Case 2: finding cites page 1's Bates number -> must land on page 1, show "match".
                page_info, cls, text, hl = run_case(page, session_id, filename, PAGE1_BATES, "cites_page1")
                print(f"[cites page 1 bates] viewer shows: {page_info!r}")
                print(f"  banner class={cls!r}")
                print(f"  banner text={text!r}")
                print(f"  highlight boxes drawn: {hl}")
                ok2 = "Page 1" in page_info and "match" in cls and "mismatch" not in cls
                print(f"  -> {'PASS' if ok2 else 'FAIL'} (expected page 1 + match banner)\n")
                all_ok &= ok2

                # Case 3: finding cites a Bates number that appears on NEITHER page -> should still
                # land on some page (first exact match, since no preferred candidate exists) but the
                # banner must say "mismatch", never silently claim a match.
                page_info, cls, text, hl = run_case(page, session_id, filename, NONEXISTENT_BATES, "cites_nonexistent")
                print(f"[cites nonexistent bates] viewer shows: {page_info!r}")
                print(f"  banner class={cls!r}")
                print(f"  banner text={text!r}")
                print(f"  highlight boxes drawn: {hl}")
                ok3 = "mismatch" in cls
                print(f"  -> {'PASS' if ok3 else 'FAIL'} (expected mismatch banner, never a false match)\n")
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
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
