#!/usr/bin/env python3
"""
Drives the actual running web app with a real browser (Playwright + Chromium) and checks that
PDF highlight boxes actually land on top of real rendered text, rather than just trusting the code.

Usage: .venv/bin/python verify_highlighting.py [zip_path] [--headed]
Requires the Flask app already running on http://127.0.0.1:5050.
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
DEFAULT_ZIP = BASE / "sample_data" / "case_000_pdfs.zip"
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
# Deliberately a different port from the one a person would actually use (5050). This app instance
# is dedicated to automated testing — see start_test_server.sh — so test runs never delete session
# files out from under someone's live session on 5050.
APP_URL = "http://127.0.0.1:5051"


def main():
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else DEFAULT_ZIP
    headed = "--headed" in sys.argv
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.add_init_script("window.__LFA_DEBUG_QUOTE_MATCH = true;")
        console_errors = []
        debug_logs = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("console", lambda msg: debug_logs.append(msg.text) if "QUOTE MATCH DEBUG" in msg.text else None)
        page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))
        page.on("response", lambda resp: console_errors.append(f"HTTP {resp.status}: {resp.url}")
                 if resp.status >= 400 else None)

        # Capture the exact /analyze response this run gets, so a failure can be diagnosed against
        # the actual quotes THIS run produced — model output is non-deterministic, so a fresh curl
        # call afterward would very likely get different quotes and not reproduce the failure.
        captured = {}

        def capture_analyze(response):
            if "/analyze" in response.url:
                try:
                    body = response.body().decode("utf-8")
                    last_line = [ln for ln in body.splitlines() if ln.strip()][-1]
                    captured["findings"] = json.loads(last_line).get("findings")
                except Exception:
                    pass

        page.on("response", capture_analyze)

        print(f"Navigating to {APP_URL} ...")
        page.goto(f"{APP_URL}/review")

        print(f"Uploading {zip_path.name} ...")
        page.set_input_files("#zipfile", str(zip_path))
        page.click("#submit-btn")

        print("Waiting for analysis to complete (this can take 20-120s)...")
        page.wait_for_selector("#results", state="visible", timeout=180_000)
        page.wait_for_selector(".finding", timeout=10_000)

        all_quotes = []
        if captured.get("findings"):
            f = captured["findings"]
            for item in f.get("timeline", []) + f.get("potential_issues", []):
                all_quotes.append(item.get("quote"))
            for item in f.get("discrepancies", []):
                all_quotes.extend(item.get("quotes", []))

        findings = page.locator(".finding")
        count = findings.count()
        print(f"Found {count} finding(s) in the results list.")

        all_ok = True
        for i in range(count):
            finding = findings.nth(i)
            finding_text = finding.inner_text().replace("\n", " ")[:70]
            has_quote = finding.locator(".finding-no-quote").count() == 0
            # A plain row click is a lightweight selection only now (see app.js selectFinding) —
            # loading the PDF/highlight requires the citation chip specifically. A finding with no
            # quote has no citation chip at all, so the row click is the only option there, and is
            # sufficient to verify no stale highlight appears (the actual thing being tested below).
            citation = finding.locator(".finding-citation")
            if citation.count():
                citation.click()
            else:
                finding.click()

            # Give the async load/search/render chain a moment to settle.
            page.wait_for_timeout(800)
            highlight_count = page.locator(".pdf-highlight").count()

            if not has_quote:
                # This finding has no quote at all — the viewer must NOT still be showing a
                # highlight left over from whichever finding was selected before this one.
                ok = highlight_count == 0
                if not ok:
                    all_ok = False
                print(f"  [{i}] '{finding_text}' -> no quote for this finding, "
                      f"{'correctly showed no highlight' if ok else 'STALE HIGHLIGHT STILL VISIBLE (bug)'}")
                screenshot_path = SCREENSHOT_DIR / f"finding_{i}.png"
                page.locator(".viewer-pane").screenshot(path=str(screenshot_path))
                continue

            if highlight_count == 0:
                hint = page.locator("#viewer-hint").inner_text()
                actual_quote = all_quotes[i] if i < len(all_quotes) else "(quote unknown)"
                diagnosis = diagnose_quote(actual_quote, zip_path) if actual_quote else "(quote unknown)"
                print(f"  [{i}] '{finding_text}' -> NO HIGHLIGHT ({hint})")
                print(f"        quote was: {actual_quote!r} -> {diagnosis}")
                screenshot_path = SCREENSHOT_DIR / f"finding_{i}.png"
                page.locator(".viewer-pane").screenshot(path=str(screenshot_path))
                continue

            highlight_boxes = page.locator(".pdf-highlight")
            text_spans = page.locator("#text-layer span")

            hl_box = highlight_boxes.first.bounding_box()
            # Both layers sit at the same position/size over the canvas, so a correctly-computed
            # highlight box should closely MATCH one specific span's box (not just loosely overlap
            # several) — this is a much stronger check than "is it near some text somewhere."
            best_match_px = None
            for j in range(text_spans.count()):
                span_box = text_spans.nth(j).bounding_box()
                if not span_box:
                    continue
                diff = box_edge_diff(hl_box, span_box)
                if best_match_px is None or diff < best_match_px:
                    best_match_px = diff

            close_match = best_match_px is not None and best_match_px <= 4
            status = "OK" if close_match else "MISALIGNED"
            if not close_match:
                all_ok = False
            closest = f"{best_match_px:.1f}px off nearest span" if best_match_px is not None else "no spans found"
            print(f"  [{i}] '{finding_text}' -> highlight {status} ({closest}) "
                  f"(box: {round(hl_box['x'])},{round(hl_box['y'])} "
                  f"{round(hl_box['width'])}x{round(hl_box['height'])})")

            screenshot_path = SCREENSHOT_DIR / f"finding_{i}.png"
            page.locator(".viewer-pane").screenshot(path=str(screenshot_path))

        browser.close()

        if debug_logs:
            print(f"\n{len(debug_logs)} quote-match failure(s) with full debug detail:")
            for log in debug_logs:
                payload = json.loads(log[len("QUOTE MATCH DEBUG "):])
                quote = payload["normalizedQuote"]
                print(f"  normalized quote: {quote!r}")
                # `pages` is one combined-text string per page of the document (see the
                # `pages.map((p) => p.combined)` debug log in app.js) — every page gets checked
                # since the quote may belong to any of them, not just the first.
                found_on_any_page = any(quote in combined for combined in payload["pages"])
                print(f"  quote found verbatim on any page (substring check): {found_on_any_page}")
                if not found_on_any_page:
                    print(f"  ({len(payload['pages'])} page(s) searched, quote not found verbatim on any of them)")
                print()

        print()
        if console_errors:
            print(f"Console errors seen during run ({len(console_errors)}):")
            for e in console_errors[:10]:
                print(f"  - {e}")
        else:
            print("No console errors during run.")

        print()
        print("PASS" if all_ok and not console_errors else "FAIL")
        return 0 if all_ok and not console_errors else 1


def normalize_py(s):
    """Mirrors the JS normalize() in app.js — keep these two in sync by hand."""
    s = re.sub(r"""['"`‘’“”]""", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def diagnose_quote(quote, zip_path):
    """Checks a failed quote against the case's source markdown to explain why it didn't match."""
    src_path = zip_path.parent / zip_path.name.replace("_pdfs.zip", "_raw_records.md")
    if not src_path.exists():
        return "no source markdown found to diagnose against"
    source = src_path.read_text()
    if quote in source:
        return "EXACT match exists in source — likely a page-search or item-splitting bug, not a text mismatch"
    if normalize_py(quote) in normalize_py(source):
        return "matches after normalization — should have been found; investigate the JS matching logic"
    return "genuinely does not appear in source, even normalized — the model paraphrased instead of quoting verbatim"


def box_edge_diff(a, b):
    """Sum of absolute differences between each box's edges, in pixels — 0 means an exact match."""
    return (
        abs(a["x"] - b["x"])
        + abs(a["y"] - b["y"])
        + abs((a["x"] + a["width"]) - (b["x"] + b["width"]))
        + abs((a["y"] + a["height"]) - (b["y"] + b["height"]))
    )


if __name__ == "__main__":
    sys.exit(main())
