#!/usr/bin/env python3
"""
Comprehensive highlighting regression test across two full, real, multi-document Case Mode
fixtures (case_ferreira and case_whitfield — see scripts/make_case_test_folders.py), each with the
same 10-subfolder structure as case_smith but genuinely different content (different plaintiff,
defendant, facts, and medical record scenario per case), all Bates-stamped.

For each case: starts a real /case/start run, waits for it to finish, opens a fresh review page,
and clicks through EVERY finding that has a citation — not a sample, all of them across both cases
— checking three things per finding:
  1. A highlight box actually appears.
  2. It aligns precisely (within a few pixels) to a real rendered text span from pdf.js's own
     TextLayer — the same strict check verify_highlighting.py uses.
  3. The Bates cross-check banner (see showFinding/findQuoteInDoc in app.js) never shows
     "mismatch" — the concrete, mechanically-detected signal that the wrong page is being shown.

This is the "it needs to be perfect" bar: ANY misaligned highlight or ANY Bates mismatch is treated
as a hard failure, across every single citable finding in both cases, not a spot check.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh), and
the two fixtures already generated (scripts/make_case_test_folders.py's build_case_ferreira/
build_case_whitfield).

Usage: testing/.venv/bin/python testing/verify_case_highlighting_regression.py [--headed]
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from case_upload_helpers import urllib_start_case

APP_URL = "http://127.0.0.1:5051"
BASE = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
MAX_WAIT_S = 20 * 60

CASES = [
    {"name": "case_ferreira", "plaintiff": "Daniel R. Ferreira", "folder": BASE / "sample_data" / "case_ferreira"},
    {"name": "case_whitfield", "plaintiff": "Linda K. Whitfield-Nakamura", "folder": BASE / "sample_data" / "case_whitfield"},
]


def start_case(plaintiff_name: str, folder: Path) -> str:
    return urllib_start_case(APP_URL, plaintiff_name, folder, priority_hint="records", timeout=120)


def get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def wait_for_done(job_id: str) -> dict:
    start = time.time()
    while time.time() - start < MAX_WAIT_S:
        _, manifest = get_json(f"{APP_URL}/case/status/{job_id}")
        if manifest.get("status") == "done":
            return manifest
        time.sleep(10)
    raise TimeoutError(f"job {job_id} never finished within {MAX_WAIT_S}s")


def box_edge_diff(a, b):
    return (
        abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])
        + abs((a["x"] + a["width"]) - (b["x"] + b["width"]))
        + abs((a["y"] + a["height"]) - (b["y"] + b["height"]))
    )


def check_case(browser, case_name: str, job_id: str, group_key: str) -> bool:
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    console_errors = []
    page.on("pageerror", lambda e: console_errors.append(f"[PAGEERROR] {e}"))
    page.on("console", lambda m: console_errors.append(f"[console.error] {m.text}") if m.type == "error" else None)

    url = f"{APP_URL}/review?case={job_id}&group={group_key}"
    page.goto(url)
    page.wait_for_selector(".finding", timeout=30_000)

    findings = page.locator(".finding")
    count = findings.count()
    print(f"\n=== {case_name}: {count} finding(s) ===")

    all_ok = True
    checked = 0
    for i in range(count):
        finding = findings.nth(i)
        finding_text = finding.inner_text().replace("\n", " ")[:70]
        citation = finding.locator(".finding-citation")
        if citation.count() == 0:
            continue  # no quote to check — nothing to highlight
        checked += 1

        citation.click()
        page.wait_for_timeout(900)

        highlight_boxes = page.locator(".pdf-highlight")
        highlight_count = highlight_boxes.count()
        banner_class = page.locator("#viewer-bates-check").get_attribute("class") or ""
        banner_text = page.locator("#viewer-bates-check").inner_text() if page.locator("#viewer-bates-check").count() else ""

        if highlight_count == 0:
            hint = page.locator("#viewer-hint").inner_text()
            print(f"  [{i}] '{finding_text}' -> NO HIGHLIGHT ({hint})")
            print(f"        bates banner: {banner_class!r} {banner_text!r}")
            all_ok = False
            page.locator(".viewer-pane").screenshot(path=str(SCREENSHOT_DIR / f"{case_name}_finding_{i}_nohighlight.png"))
            continue

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
        aligned = best_diff is not None and best_diff <= 4
        mismatch = "mismatch" in banner_class

        status = "OK" if (aligned and not mismatch) else "FAIL"
        print(f"  [{i}] '{finding_text}' -> {status} "
              f"(align={best_diff:.1f}px off, banner={'mismatch!' if mismatch else banner_class.split()[-1] if banner_class else 'n/a'})")
        if not aligned or mismatch:
            all_ok = False
            print(f"        banner text: {banner_text!r}")
            page.locator(".viewer-pane").screenshot(path=str(SCREENSHOT_DIR / f"{case_name}_finding_{i}_fail.png"))

    print(f"{case_name}: checked {checked} citable finding(s) of {count} total")

    if console_errors:
        print(f"Console errors seen during run ({len(console_errors)}):")
        for e in console_errors[:10]:
            print(f"  - {e}")
        all_ok = False
    else:
        print("No console errors during run.")

    page.close()
    return all_ok


def main():
    headed = "--headed" in sys.argv
    all_ok = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            for case in CASES:
                if not case["folder"].is_dir():
                    print(f"FAIL: {case['folder']} does not exist — run scripts/make_case_test_folders.py first")
                    return 1

                print(f"Starting real case run: {case['name']} (plaintiff: {case['plaintiff']})...")
                job_id = start_case(case["plaintiff"], case["folder"])
                manifest = wait_for_done(job_id)
                group_key = next(iter(manifest.get("groups", {})), None)
                if not group_key:
                    print(f"FAIL: {case['name']} finished with no groups at all")
                    all_ok = False
                    continue

                ok = check_case(browser, case["name"], job_id, group_key)
                all_ok &= ok
        finally:
            browser.close()

    print()
    print("OVERALL:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
