#!/usr/bin/env python3
"""
Harder trap than verify_bates_disambiguation.py: a 5-page document where the SAME common sentence
("Patient tolerated the visit well with no acute distress noted.") is repeated verbatim on every
single page (a very real pattern — templated EHR boilerplate), each page with its own Bates
number. Proves the app picks the page matching the finding's cited Bates even when there are
FIVE exact textual matches to choose from, not just two.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_repeated_boilerplate_disambiguation.py [--headed]
"""
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

BATES_START = 700  # pages -> MED000700 .. MED000704
NUM_PAGES = 5
REPEATED_QUOTE = "Patient tolerated the visit well with no acute distress noted."
UNIQUE_LINES = [
    "Follow up in two weeks for suture removal.",
    "Follow up in two weeks for repeat labs.",
    "Follow up in two weeks for wound check.",
    "Follow up in two weeks for medication review.",
    "Follow up in two weeks for final clearance.",
]


class BatesPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        bates = f"MED{BATES_START + self.page_no() - 1:06d}"
        self.set_x(0)
        self.cell(self.w, 10, bates, align="C")


def build_pdf(dest: Path):
    pdf = BatesPDF()
    for i, unique_line in enumerate(UNIQUE_LINES):
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.write(6, "CONFIDENTIAL - FOR INTERNAL USE ONLY - DO NOT DISTRIBUTE\n")
        pdf.write(6, f"PROGRESS NOTE - VISIT {i + 1}\n")
        pdf.write(6, f"Date: 01/0{i + 1}/2026\nAuthor: Dr. A. Nguyen\n\n")
        pdf.write(6, f"{REPEATED_QUOTE}\n\n")
        pdf.write(6, f"{unique_line}\n")
    pdf.output(str(dest))


def bates_for_page(page_num_1_indexed: int) -> str:
    return f"MED{BATES_START + page_num_1_indexed - 1:06d}"


def run_case(page, session_id, filename, target_page_num, label):
    cited_bates = bates_for_page(target_page_num)
    fake_result = {
        "session_id": session_id,
        "ocr_files": [],
        "record_source_labels": {filename: "BoilerplateRecord"},
        "warnings": [],
        "stats": {
            "documents_processed": 1, "total_pages": NUM_PAGES, "wall_time_seconds": 0,
            "tokens_per_second": None, "model": "test-fixture", "detail_level": "standard",
        },
        "findings": {
            "timeline": [{
                "date": f"01/0{target_page_num}/2026",
                "text": f"Visit {target_page_num}: patient tolerated well, {UNIQUE_LINES[target_page_num - 1].lower()}",
                "source_file": filename,
                "quote": REPEATED_QUOTE,
                "record_type": "Progress Note",
                "author": "Dr. A. Nguyen",
                "at_issue": False,
                "bates": cited_bates,
            }],
            "potential_issues": [], "discrepancies": [], "key_facts": {},
        },
    }
    page.goto(f"{APP_URL}/review")
    page.evaluate(
        "(data) => sessionStorage.setItem('lawfirmagent_last_result', JSON.stringify(data))",
        fake_result,
    )
    page.reload()
    page.wait_for_selector(".finding", timeout=10_000)
    page.locator(".finding-citation").first.click()
    page.wait_for_timeout(1000)

    page_info = page.locator("#viewer-page-info").inner_text()
    banner = page.locator("#viewer-bates-check")
    banner_class = banner.get_attribute("class") or ""
    banner_text = banner.inner_text() if banner.count() else ""
    highlight_count = page.locator(".pdf-highlight").count()

    screenshot_path = SCREENSHOT_DIR / f"boilerplate_trap_{label}.png"
    page.locator(".viewer-pane").screenshot(path=str(screenshot_path))
    return cited_bates, page_info, banner_class, banner_text, highlight_count


def main():
    headed = "--headed" in sys.argv
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    session_id = uuid.uuid4().hex
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    filename = "boilerplate_record.pdf"
    pdf_path = session_dir / filename
    try:
        build_pdf(pdf_path)
        print(f"Built {NUM_PAGES}-page repeated-boilerplate PDF at {pdf_path}")
        print(f"Repeated verbatim quote on EVERY page: {REPEATED_QUOTE!r}\n")

        all_ok = True
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                console_errors = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

                # Test every single page as the "target" -- proves disambiguation isn't luckily
                # correct only for the first or last candidate.
                for target in range(1, NUM_PAGES + 1):
                    cited_bates, page_info, cls, text, hl = run_case(page, session_id, filename, target, f"p{target}")
                    expected_page_str = f"Page {target} of {NUM_PAGES}"
                    ok = (page_info == expected_page_str) and ("match" in cls) and ("mismatch" not in cls) and hl > 0
                    print(f"[target page {target}, cites {cited_bates}] viewer shows {page_info!r}, "
                          f"banner={cls!r}, highlights={hl} -> {'PASS' if ok else 'FAIL'}")
                    if not ok:
                        print(f"    banner text: {text!r}")
                    all_ok &= ok

                if console_errors:
                    print(f"\nConsole errors seen during run ({len(console_errors)}):")
                    for e in console_errors[:10]:
                        print(f"  - {e}")
                    all_ok = False
                else:
                    print("\nNo console errors during run.")
            finally:
                browser.close()

        print()
        print("PASS" if all_ok else "FAIL")
        return 0 if all_ok else 1
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
