#!/usr/bin/env python3
"""
Generates a fake "scanned" PDF -- a page rendered as an IMAGE with no underlying text layer, the
same way a faxed/scanned outside-provider record would look to our extraction pipeline. Used to
test whether the OCR fallback actually works, since our other test PDFs all have real text layers.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / "sample_data" / "case_005_pdfs"
OUT_ZIP = BASE / "sample_data" / "case_005_pdfs.zip"

TEXT = """SYNTHETIC TEST DATA - NOT A REAL PATIENT

Crestline Family Medicine - Office Visit
Date of Service: 03/15/2026
Provider: Dr. M. Okafor-Ellis

Chief complaint: Follow-up for hypertension.

HPI: 58-year-old male returns for routine blood pressure follow-up. Reports
occasional headaches in the mornings over the past two weeks. Denies chest
pain, vision changes, or shortness of breath. Currently taking lisinopril
20mg once daily.

Exam: Blood pressure 162/98, repeated at 158/96. Heart rate 76 and regular.
No peripheral edema. Fundoscopic exam deferred.

Assessment: Hypertension, poorly controlled on current regimen despite
medication compliance per patient report.

Plan: Increase lisinopril to 40mg once daily. Recheck blood pressure in
2 weeks. Basic metabolic panel ordered to assess renal function given
dose increase. Counseled on low-sodium diet and home blood pressure
monitoring twice daily with a log to bring to next visit."""


def make_scanned_page(text: str, out_path: Path):
    width, height = 1700, 2200  # roughly 8.5x11in at ~200dpi, like a real scanned page
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except OSError:
        font = ImageFont.load_default()

    margin = 120
    y = margin
    for line in text.split("\n"):
        draw.text((margin, y), line, fill="black", font=font)
        y += 48

    # Save as a single-page PDF made entirely from this image -- no text layer at all, exactly
    # like a real scan/fax would produce.
    img.save(out_path, "PDF", resolution=200.0)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = OUT_DIR / "record_01.pdf"
    make_scanned_page(TEXT, out_pdf)
    print(f"wrote {out_pdf}")

    import zipfile
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_pdf, arcname=out_pdf.name)
    print(f"zipped -> {OUT_ZIP}")


if __name__ == "__main__":
    main()
