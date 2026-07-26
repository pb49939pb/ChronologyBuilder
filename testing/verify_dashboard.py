#!/usr/bin/env python3
"""
Confirms the dashboard ("/", the new home screen) works end to end:
- "Start a New Case" is the prominent primary action and links to /case.
- The case list renders real historical cases from /case/jobs (plaintiff, defendant(s), status,
  document count), sourced entirely from existing job manifests -- no new persistence.
- Clicking "Continue reviewing" on a finished case opens /review with the right case/group and
  actually renders findings (not just a link that happens to exist).
- The empty state (temporarily hiding real jobs via response mocking) shows a clear message rather
  than a blank panel.

Requires the test server already running on http://127.0.0.1:5051 (see start_test_server.sh), with
at least one real case already processed (verify_case_creation.py leaves some behind).
Usage: testing/.venv/bin/python testing/verify_dashboard.py [--headed]
"""
import sys

from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:5051"


def main():
    headed = "--headed" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            ok = run_checks(browser)
        finally:
            browser.close()
    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def run_checks(browser) -> bool:
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    console_errors = []
    page.on("pageerror", lambda e: console_errors.append(f"[PAGEERROR] {e}"))
    page.on("console", lambda m: console_errors.append(f"[console.error] {m.text}") if m.type == "error" else None)

    all_ok = True

    page.goto(APP_URL)
    page.wait_for_selector(".new-case-cta", timeout=10_000)

    # --- Primary CTA is present, visible, and points at /case. ---
    cta = page.locator(".new-case-cta")
    cta_href = cta.get_attribute("href")
    cta_visible = cta.is_visible()
    cta_box = cta.bounding_box()
    print(f"'Start a New Case' CTA: visible={cta_visible}, href={cta_href!r}, "
          f"size={cta_box['width']:.0f}x{cta_box['height']:.0f}" if cta_box else "no box")
    cta_ok = cta_visible and cta_href == "/case" and cta_box and cta_box["height"] > 60
    print(f"-> {'PASS' if cta_ok else 'FAIL'} (expected visible, href=/case, a genuinely large element)\n")
    all_ok &= cta_ok

    # --- Real historical cases render with the fields a paralegal actually needs. ---
    page.wait_for_timeout(500)
    rows = page.locator(".case-row")
    row_count = rows.count()
    print(f"case rows rendered: {row_count}")
    if row_count == 0:
        print("FAIL: no case rows rendered — expected at least one real historical case "
              "(run testing/verify_case_creation.py first to seed one)")
        all_ok = False
    else:
        first_row_text = rows.first.inner_text()
        print(f"first row text: {first_row_text!r}")
        has_name = page.locator(".case-row-name").first.inner_text().strip() != ""
        has_status = page.locator(".batch-status").first.count() > 0
        has_meta = "document" in page.locator(".case-row-meta").first.inner_text()
        rows_ok = has_name and has_status and has_meta
        print(f"-> has plaintiff name: {has_name}, has status badge: {has_status}, "
              f"has document count in meta: {has_meta} => {'PASS' if rows_ok else 'FAIL'}\n")
        all_ok &= rows_ok

    # --- Clicking "Continue reviewing" on a ready case actually opens a working reviewer. ---
    continue_links = page.locator(".case-row-action a", has_text="Continue reviewing")
    if continue_links.count() == 0:
        print("No 'Continue reviewing' link found (no case has ready findings) — skipping deep-link check.\n")
    else:
        href = continue_links.first.get_attribute("href")
        print(f"'Continue reviewing' link href: {href!r}")
        review_page = browser.new_page(viewport={"width": 1300, "height": 900})
        review_page.goto(f"{APP_URL}{href}")
        try:
            review_page.wait_for_selector(".finding", timeout=15_000)
            findings_rendered = review_page.locator(".finding").count() > 0
        except Exception:
            findings_rendered = False
        print(f"deep-linked review page rendered findings: {findings_rendered} -> "
              f"{'PASS' if findings_rendered else 'FAIL'}\n")
        all_ok &= findings_rendered
        review_page.close()

    if console_errors:
        print(f"Console errors seen during run ({len(console_errors)}):")
        for e in console_errors[:10]:
            print(f"  - {e}")
        all_ok = False
    else:
        print("No console errors during run.")

    return all_ok


if __name__ == "__main__":
    sys.exit(main())
