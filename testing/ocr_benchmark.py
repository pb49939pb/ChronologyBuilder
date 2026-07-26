#!/usr/bin/env python3
"""
OCR benchmark harness: runs the synthetic hard-case test PDFs (sample_data/ocr_test_cases/)
through easyocr under different configurations (CPU vs MPS GPU, resolution, preprocessing) and
scores each against ground truth using Word Error Rate (WER) — the standard ASR/OCR accuracy
metric (edit distance between predicted and reference word sequences, divided by reference length).

Usage: webapp/.venv/bin/python testing/ocr_benchmark.py
"""
import json
import time
from pathlib import Path

import numpy as np
import pdfplumber
from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parent.parent
CASES_DIR = BASE / "sample_data" / "ocr_test_cases"
RESULTS_DIR = BASE / "testing" / "ocr_results"


def normalize_words(text: str) -> list:
    import re
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def word_error_rate(hypothesis: str, reference: str) -> float:
    """Standard WER via Levenshtein distance over word sequences."""
    hyp = normalize_words(hypothesis)
    ref = normalize_words(reference)
    if not ref:
        return 0.0 if not hyp else 1.0

    # DP edit distance
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[n][m] / len(ref)


def deskew(image: Image.Image) -> Image.Image:
    """Cheap deskew: try a small range of rotation angles, pick the one that maximizes the
    variance of horizontal row-darkness projections (text lines produce sharp peaks/troughs when
    correctly horizontal, and a blurred/flat profile when still skewed)."""
    gray = ImageOps.grayscale(image)
    arr = np.array(gray).astype(np.float32)
    best_angle, best_score = 0, -1
    for angle in np.arange(-6, 6.5, 0.5):
        rotated = gray.rotate(angle, fillcolor=255, resample=Image.BICUBIC)
        row_sums = np.array(rotated).astype(np.float32).sum(axis=1)
        score = np.var(row_sums)
        if score > best_score:
            best_score, best_angle = score, angle
    if best_angle == 0:
        return image
    return image.rotate(best_angle, fillcolor=(255, 255, 255), resample=Image.BICUBIC)


def enhance_contrast(image: Image.Image) -> Image.Image:
    """Simple auto-contrast stretch — cheap, no ML, helps washed-out fax-style scans."""
    return ImageOps.autocontrast(image, cutoff=1)


_READER_CACHE = {}


def get_reader(gpu: bool):
    if gpu not in _READER_CACHE:
        import easyocr

        _READER_CACHE[gpu] = easyocr.Reader(["en"], gpu=gpu, verbose=False)
    return _READER_CACHE[gpu]


def run_ocr(image: Image.Image, gpu: bool) -> str:
    reader = get_reader(gpu)
    arr = np.array(image.convert("RGB"))
    lines = reader.readtext(arr, detail=0, paragraph=True)
    return "\n".join(lines)


def main():
    cases = sorted(CASES_DIR.glob("*.pdf"))
    configs = [
        {"name": "cpu_200dpi_raw", "gpu": False, "dpi": 200, "preprocess": None},
        {"name": "mps_200dpi_raw", "gpu": True, "dpi": 200, "preprocess": None},
        {"name": "mps_300dpi_raw", "gpu": True, "dpi": 300, "preprocess": None},
        {"name": "mps_200dpi_deskew_contrast", "gpu": True, "dpi": 200, "preprocess": "both"},
    ]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = []

    for case_pdf in cases:
        name = case_pdf.stem
        gt_path = CASES_DIR / f"{name}_ground_truth.txt"
        if not gt_path.exists():
            continue
        ground_truth = gt_path.read_text()

        for cfg in configs:
            with pdfplumber.open(str(case_pdf)) as pdf:
                page = pdf.pages[0]
                image = page.to_image(resolution=cfg["dpi"]).original.convert("RGB")

            if cfg["preprocess"] == "both":
                image = deskew(image)
                image = enhance_contrast(image)

            start = time.time()
            try:
                text = run_ocr(image, gpu=cfg["gpu"])
            except Exception as e:
                text = ""
                print(f"  ERROR on {name} / {cfg['name']}: {e}")
            elapsed = time.time() - start

            wer = word_error_rate(text, ground_truth)
            result = {
                "case": name,
                "config": cfg["name"],
                "wer": round(wer, 3),
                "accuracy_pct": round((1 - wer) * 100, 1),
                "seconds": round(elapsed, 2),
            }
            all_results.append(result)
            print(f"{name:30s} {cfg['name']:28s} WER={wer:.3f} ({result['accuracy_pct']}%) {elapsed:.2f}s")

    (RESULTS_DIR / "benchmark_results.json").write_text(json.dumps(all_results, indent=2))
    print(f"\nResults written to {RESULTS_DIR / 'benchmark_results.json'}")


if __name__ == "__main__":
    main()
