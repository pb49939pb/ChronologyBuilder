#!/usr/bin/env python3
"""
Generates a battery of "hard" synthetic scanned-page test PDFs for OCR testing — clean typed text
as a control, plus handwriting-style fonts and common real-world scan degradations (skew, noise,
low contrast), isolated one at a time and then combined into a worst-case. Same underlying text
across every variant so results are directly comparable, and a ground-truth .txt is saved alongside
each PDF for scoring (word error rate).

None of this is real patient handwriting (that would raise its own privacy questions even if
synthetic-patient-named) — cursive/connected system fonts are a reasonable, defensible proxy for
handwriting-recognition difficulty, not a claim of true handwriting-recognition fidelity. See
RESEARCH_NOTES.md for why this distinction matters (published accuracy figures for handwriting OCR
assume genuine handwriting, not stylized fonts — treat results here as directionally informative,
not as a literal handwriting-accuracy benchmark).
"""
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / "sample_data" / "ocr_test_cases"

GROUND_TRUTH = """SYNTHETIC TEST DATA - NOT A REAL PATIENT

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

WIDTH, HEIGHT = 1700, 2200
MARGIN = 120
LINE_HEIGHT = 48


def render_text_image(text: str, font_path: str, font_size: int, line_height: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        font = ImageFont.load_default()
    y = MARGIN
    for line in text.split("\n"):
        draw.text((MARGIN, y), line, fill="black", font=font)
        y += line_height
    return img


def add_noise(img: Image.Image, amount: float) -> Image.Image:
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, amount, arr.shape).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def reduce_contrast(img: Image.Image, factor: float) -> Image.Image:
    # factor < 1 pulls pixel values toward mid-gray, simulating a washed-out fax/copy.
    arr = np.array(img).astype(np.float32)
    arr = 128 + (arr - 128) * factor
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def save_pdf(img: Image.Image, name: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = OUT_DIR / f"{name}.pdf"
    img.convert("RGB").save(out_pdf, "PDF", resolution=200.0)
    (OUT_DIR / f"{name}_ground_truth.txt").write_text(GROUND_TRUTH)
    print(f"wrote {out_pdf}")


def main():
    random.seed(42)
    np.random.seed(42)

    helvetica = "/System/Library/Fonts/Helvetica.ttc"
    bradley_hand = "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf"
    snell_roundhand = "/System/Library/Fonts/Supplemental/SnellRoundhand.ttc"

    # 1. Clean typed control -- same as the earlier scanned-page test, for baseline comparison.
    img = render_text_image(GROUND_TRUTH, helvetica, 32, LINE_HEIGHT)
    save_pdf(img, "01_clean_typed")

    # 2. "Handwriting," legible tier -- a print-style handwriting font, otherwise clean scan.
    img = render_text_image(GROUND_TRUTH, bradley_hand, 34, LINE_HEIGHT)
    save_pdf(img, "02_handwriting_legible")

    # 3. "Handwriting," cursive/connected tier -- a genuine script font, harder to segment letters.
    img = render_text_image(GROUND_TRUTH, snell_roundhand, 40, LINE_HEIGHT)
    save_pdf(img, "03_handwriting_cursive")

    # 4. Faxed/photocopied: clean typed font, but noisy + low contrast + slightly blurred.
    img = render_text_image(GROUND_TRUTH, helvetica, 32, LINE_HEIGHT)
    img = reduce_contrast(img, 0.55)
    img = add_noise(img, 18)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    save_pdf(img, "04_faxed_noisy")

    # 5. Skewed scan: clean typed font, fed crookedly into a scanner (~4 degrees).
    img = render_text_image(GROUND_TRUTH, helvetica, 32, LINE_HEIGHT)
    img = img.rotate(4, fillcolor="white", expand=False, resample=Image.BICUBIC)
    save_pdf(img, "05_skewed_scan")

    # 6. Worst case: legible-handwriting font + skew + noise + low contrast, combined.
    img = render_text_image(GROUND_TRUTH, bradley_hand, 34, LINE_HEIGHT)
    img = img.rotate(3, fillcolor="white", expand=False, resample=Image.BICUBIC)
    img = reduce_contrast(img, 0.6)
    img = add_noise(img, 15)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    save_pdf(img, "06_worst_case_combined")

    print(f"\n{6} test cases written to {OUT_DIR}")


if __name__ == "__main__":
    main()
