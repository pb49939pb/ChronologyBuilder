#!/usr/bin/env python3
"""
Edge-case highlight test: a 2-column medical-record layout (a common real-world format not
covered by any other fixture), verifying the highlight box still lands precisely on the quoted
sentence rather than drifting into the other column or between columns. Uses the sessionStorage
restore trick (see verify_bates_disambiguation.py) so it's deterministic — no LLM call needed.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh).
Usage: testing/.venv/bin/python testing/verify_multicolumn_highlighting.py [--headed]
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

BATES = "MED000501"
TARGET_QUOTE = "Clinical presentation is consistent with acute appendicitis."

LEFT_COL = [
    "HISTORY OF PRESENT ILLNESS",
    "The patient is a 34 year old",
    "female presenting with acute",
    "onset abdominal pain radiating",
    "to the right lower quadrant,",
    "started approximately 6 hours",
    "prior to arrival.",
    "",
    "REVIEW OF SYSTEMS",
    "Denies fever, denies vomiting.",
    "Reports nausea and anorexia",
    "since onset of pain.",
]
RIGHT_COL = [
    "ASSESSMENT AND PLAN",
    "Clinical presentation is",
    "consistent with acute",
    "appendicitis. CT abdomen and",
    "pelvis with contrast was",
    "ordered and confirms findings.",
    "",
    "Surgery consult requested",
    "emergently for probable",
    "appendectomy this evening.",
]


class BatesPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        self.set_x(0)
        self.cell(self.w, 10, BATES, align="C")


def build_pdf(dest: Path):
    pdf = BatesPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    col_width = 90
    left_x, right_x = 10, 110
    y_start = 20

    pdf.set_xy(left_x, y_start)
    for line in LEFT_COL:
        pdf.set_x(left_x)
        pdf.multi_cell(col_width, 5, line)

    pdf.set_xy(right_x, y_start)
    for line in RIGHT_COL:
        pdf.set_xy(right_x, pdf.get_y() if pdf.get_y() > y_start else y_start)
        pdf.multi_cell(col_width, 5, line)
    pdf.output(str(dest))


def box_edge_diff(a, b):
    return (
        abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])
        + abs((a["x"] + a["width"]) - (b["x"] + b["width"]))
        + abs((a["y"] + a["height"]) - (b["y"] + b["height"]))
    )


def main():
    headed = "--headed" in sys.argv
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    session_id = uuid.uuid4().hex
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    filename = "multicolumn_record.pdf"
    pdf_path = session_dir / filename
    try:
        build_pdf(pdf_path)
        print(f"Built 2-column trap PDF at {pdf_path}, bates={BATES}")
        print(f"Target quote (right column, wraps 3 lines): {TARGET_QUOTE!r}\n")

        fake_result = {
            "session_id": session_id,
            "ocr_files": [],
            "record_source_labels": {filename: "MultiColRecord"},
            "warnings": [],
            "stats": {
                "documents_processed": 1, "total_pages": 1, "wall_time_seconds": 0,
                "tokens_per_second": None, "model": "test-fixture", "detail_level": "standard",
            },
            "findings": {
                "timeline": [{
                    "date": "01/05/2026",
                    "text": "Assessment consistent with acute appendicitis; surgery consulted.",
                    "source_file": filename,
                    "quote": TARGET_QUOTE,
                    "record_type": "ED Note",
                    "author": "Dr. R. Alvarez",
                    "at_issue": False,
                    "bates": BATES,
                }],
                "potential_issues": [], "discrepancies": [], "key_facts": {},
            },
        }

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
                    fake_result,
                )
                page.reload()
                page.wait_for_selector(".finding", timeout=10_000)
                page.locator(".finding-citation").first.click()
                page.wait_for_timeout(1000)

                banner = page.locator("#viewer-bates-check")
                banner_class = banner.get_attribute("class") or ""
                banner_text = banner.inner_text() if banner.count() else ""
                print(f"banner class={banner_class!r}")
                print(f"banner text={banner_text!r}")
                bates_ok = "match" in banner_class and "mismatch" not in banner_class
                print(f"  -> {'PASS' if bates_ok else 'FAIL'} (expected bates match)\n")
                all_ok &= bates_ok

                highlight_boxes = page.locator(".pdf-highlight")
                highlight_count = highlight_boxes.count()
                print(f"highlight boxes drawn: {highlight_count}")
                if highlight_count == 0:
                    print("  -> FAIL (no highlight at all)")
                    all_ok = False
                else:
                    text_spans = page.locator("#text-layer span")
                    hl_box = highlight_boxes.first.bounding_box()
                    best_diff = None
                    for j in range(text_spans.count()):
                        span_box = text_spans.nth(j).bounding_box()
                        if not span_box:
                            continue
                        diff = box_edge_diff(hl_box, span_box)
                        if best_diff is None or diff < best_diff:
                            best_diff = diff
                    close_match = best_diff is not None and best_diff <= 4
                    print(f"  closest text-span match: {best_diff:.1f}px off" if best_diff is not None else "  no spans found")
                    # The trap: a badly-drifted highlight box would land near the LEFT column
                    # instead (x much smaller) since both columns contain overlapping vocabulary
                    # ("acute", "onset") -- check the box's x-position is in the right column's
                    # rendered range, not just "close to some span somewhere."
                    page_width = page.locator("#pdf-canvas").bounding_box()["width"]
                    in_right_half = hl_box["x"] > page_width * 0.45
                    print(f"  highlight box x={hl_box['x']:.0f} (page width {page_width:.0f}) "
                          f"-> {'right column' if in_right_half else 'LEFT COLUMN (WRONG)'}")
                    ok = close_match and in_right_half
                    print(f"  -> {'PASS' if ok else 'FAIL'}")
                    all_ok &= ok

                screenshot_path = SCREENSHOT_DIR / "multicolumn_trap.png"
                page.locator(".viewer-pane").screenshot(path=str(screenshot_path))

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
