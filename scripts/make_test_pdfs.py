#!/usr/bin/env python3
"""
Dev helper: splits a sample_data/<case>_raw_records.md file into one PDF per record
and zips them, so there's a ready-made test file for the web app's upload flow.
Not part of the app itself — just for generating test input.

Every page gets a Bates stamp in the bottom margin (position rotates left/center/right across
documents, matching real productions where placement varies) — sequential across the WHOLE case,
not reset per document, matching how real Bates numbering works. The app is built assuming every
real PDF it processes has one of these (see _extract_bates_number in webapp/app.py); test data has
to actually have them for that assumption to be exercised rather than silently untested.

Usage: python3 make_test_pdfs.py [case_name ...]
  (defaults to all case_*_raw_records.md files found in sample_data/)
"""
import re
import sys
import zipfile
from pathlib import Path

from fpdf import FPDF

BASE = Path(__file__).resolve().parent.parent
SAMPLE_DATA = BASE / "sample_data"

BATES_PREFIX = "MED"
_POSITIONS = ("right", "left", "center")  # rotated across documents


class BatesPDF(FPDF):
    def __init__(self, bates_start: int, position: str):
        super().__init__()
        self.bates_start = bates_start
        self.bates_position = position

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        bates_str = f"{BATES_PREFIX}{self.bates_start + self.page_no() - 1:06d}"
        if self.bates_position == "left":
            self.set_x(10)
            self.cell(40, 10, bates_str, align="L")
        elif self.bates_position == "center":
            self.set_x(0)
            self.cell(self.w, 10, bates_str, align="C")
        else:
            self.set_x(-50)
            self.cell(40, 10, bates_str, align="R")


def make_pdf(text: str, out_path: Path, bates_start: int, position: str) -> int:
    # Replace characters outside latin-1 (e.g. em-dashes) rather than pulling in a Unicode font -
    # this is just a dev helper for generating test PDFs, not the app itself.
    text = text.replace("—", "-").replace("–", "-")
    pdf = BatesPDF(bates_start, position)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in text.split("\n"):
        pdf.write(6, line + "\n")
    pdf.output(str(out_path))
    return pdf.page_no()  # pages actually used — caller advances the bates counter by this much


def build_case(case_name: str):
    src = SAMPLE_DATA / f"{case_name}_raw_records.md"
    if not src.exists():
        print(f"skipping {case_name}: {src.name} not found")
        return

    out_dir = SAMPLE_DATA / f"{case_name}_pdfs"
    out_zip = SAMPLE_DATA / f"{case_name}_pdfs.zip"

    content = src.read_text()
    sections = re.split(r"\n(?=### Record \d+)", content)

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_paths = []
    bates_counter = 1

    for i, section in enumerate([s for s in sections if re.match(r"### Record \d+ — ", s)]):
        m = re.match(r"### Record (\d+) — (.+)", section)
        record_num, _title = m.group(1), m.group(2)
        out_path = out_dir / f"record_{int(record_num):02d}.pdf"
        position = _POSITIONS[i % len(_POSITIONS)]
        pages_used = make_pdf(section.strip(), out_path, bates_counter, position)
        bates_counter += pages_used
        pdf_paths.append(out_path)
        print(f"  wrote {out_path.name} (bates {position}, {pages_used} page(s))")

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in pdf_paths:
            zf.write(p, arcname=p.name)

    print(f"  zipped {len(pdf_paths)} PDFs -> {out_zip.name}\n")


def main():
    if len(sys.argv) > 1:
        case_names = sys.argv[1:]
    else:
        case_names = sorted(
            p.name[: -len("_raw_records.md")]
            for p in SAMPLE_DATA.glob("case_*_raw_records.md")
        )

    for case_name in case_names:
        print(f"{case_name}:")
        build_case(case_name)


if __name__ == "__main__":
    main()
