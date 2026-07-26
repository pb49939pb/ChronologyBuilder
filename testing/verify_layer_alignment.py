#!/usr/bin/env python3
"""
Regression test for the specific bug class found 2026-07-21: the PDF canvas, the invisible
text-measurement layer, and the highlight overlay can silently drift to different sizes/positions:
- pdf.js's TextLayer internally overwrites its container's size via a calc() expression tied to
  undefined CSS custom properties, resolving to a wrong size instead of erroring.
- The canvas is centered by the outer flex container (justify-content: center), but the overlay
  layers were pinned via `position: absolute; left: 0` to the CONTAINER's edge rather than the
  canvas's own (centered, therefore offset) position — invisible at narrow viewport widths where
  the centering offset happens to be ~0, and present at every wider, more realistic width.

Tests across several browser window widths, INCLUDING narrow ones, and — more realistically —
resizes a SINGLE already-rendered page rather than re-uploading per width (faster, and also checks
the real-world case of a user resizing their window after a highlight is already shown, which the
per-width-reupload approach doesn't exercise).

Usage: .venv/bin/python verify_layer_alignment.py [zip_path]
Requires the dedicated test server (testing/start_test_server.sh) already running.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
DEFAULT_ZIP = BASE / "sample_data" / "case_000_pdfs.zip"
APP_URL = "http://127.0.0.1:5051"

# Deliberately includes narrow widths (the exact condition that hid the position bug) alongside
# the wide ones that are the realistic common case.
VIEWPORT_WIDTHS = [700, 900, 1100, 1400, 1800]


def sizes_match(a, b, tol=1.0):
    return abs(a["w"] - b["w"]) <= tol and abs(a["h"] - b["h"]) <= tol and \
        abs(a["x"] - b["x"]) <= tol and abs(a["y"] - b["y"]) <= tol


def best_span_match_px(hl_box, span_boxes):
    if not hl_box or not span_boxes:
        return None
    best = None
    for b in span_boxes:
        diff = (
            abs(hl_box["x"] - b["x"]) + abs(hl_box["y"] - b["y"])
            + abs((hl_box["x"] + hl_box["width"]) - (b["x"] + b["width"]))
            + abs((hl_box["y"] + hl_box["height"]) - (b["y"] + b["height"]))
        )
        if best is None or diff < best:
            best = diff
    return best


def measure(page):
    info = page.evaluate("""() => {
        const c = document.getElementById('pdf-canvas');
        const t = document.getElementById('text-layer');
        const h = document.getElementById('highlight-layer');
        const cRect = c.getBoundingClientRect();
        const tRect = t.getBoundingClientRect();
        const hRect = h.getBoundingClientRect();
        return {
            canvas: {w: cRect.width, h: cRect.height, x: cRect.left, y: cRect.top},
            textLayer: {w: tRect.width, h: tRect.height, x: tRect.left, y: tRect.top},
            highlightLayer: {w: hRect.width, h: hRect.height, x: hRect.left, y: hRect.top},
        };
    }""")
    highlight_count = page.locator(".pdf-highlight").count()
    hl_box = page.locator(".pdf-highlight").first.bounding_box() if highlight_count else None
    span_boxes = []
    if highlight_count:
        spans = page.locator("#text-layer span")
        for j in range(spans.count()):
            b = spans.nth(j).bounding_box()
            if b:
                span_boxes.append(b)
    return info, hl_box, span_boxes


def main():
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ZIP
    all_ok = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTHS[0], "height": 900})
        console_errors = []
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        print(f"Uploading {zip_path.name} once, then resizing across {VIEWPORT_WIDTHS} ...")
        page.goto(f"{APP_URL}/review")
        page.set_input_files("#zipfile", str(zip_path))
        page.click("#submit-btn")
        page.wait_for_selector("#results", state="visible", timeout=180_000)
        # A plain row click is now a lightweight selection only (see app.js selectFinding) —
        # loading the PDF/highlight requires clicking the citation chip specifically, matching the
        # new "citation-first, PDF on demand" review flow.
        page.locator(".finding-citation").first.click()
        page.wait_for_timeout(1000)

        for width in VIEWPORT_WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(300)  # let layout settle

            info, hl_box, span_boxes = measure(page)
            layers_match = (
                sizes_match(info["canvas"], info["textLayer"])
                and sizes_match(info["canvas"], info["highlightLayer"])
            )
            match_px = best_span_match_px(hl_box, span_boxes)
            highlight_ok = match_px is not None and match_px <= 4
            ok = layers_match and highlight_ok
            all_ok = all_ok and ok

            status = "PASS" if ok else "FAIL"
            print(f"[viewport width={width}px] {status}")
            print(f"  canvas:          {info['canvas']}")
            print(f"  text-layer:      {info['textLayer']}")
            print(f"  highlight-layer: {info['highlightLayer']}")
            print(f"  layers same size/position: {layers_match}")
            print(f"  highlight-vs-span match: "
                  f"{f'{match_px:.1f}px off' if match_px is not None else 'no highlight found'}")
            print()

        page.close()
        browser.close()

    if console_errors:
        print(f"Console errors during run: {console_errors}")
        all_ok = False

    print("=" * 40)
    print("OVERALL:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
