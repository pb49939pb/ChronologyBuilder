#!/usr/bin/env python3
"""One-shot: runs an analysis, then immediately dumps text items for a given record to debug a
specific quote-matching failure, all in the same browser session so nothing gets wiped in between."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
APP_URL = "http://127.0.0.1:5051"


def main():
    zip_path = BASE / "sample_data" / "case_001_pdfs.zip"
    target_file = sys.argv[1] if len(sys.argv) > 1 else "record_06.pdf"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{APP_URL}/review")
        page.set_input_files("#zipfile", str(zip_path))
        page.click("#submit-btn")
        page.wait_for_selector("#results", state="visible", timeout=180_000)

        session_id = page.evaluate("window.__lastSessionIdForDebug || null")
        # app.js doesn't expose this globally, so pull it from a finding's fetch instead:
        # simplest reliable route: read it back out of sessionStorage, which app.js already writes.
        session_id = page.evaluate("""() => {
            const raw = sessionStorage.getItem('lawfirmagent_last_result');
            return raw ? JSON.parse(raw).session_id : null;
        }""")
        print(f"session_id: {session_id}")

        pdf_url = f"{APP_URL}/session/{session_id}/pdf/{target_file}"
        result = page.evaluate(
            """async (pdfUrl) => {
                const pdfjsLib = await import('/static/pdfjs/pdf.min.mjs');
                const doc = await pdfjsLib.getDocument({ url: new URL(pdfUrl) }).promise;
                const page1 = await doc.getPage(1);
                const tc = await page1.getTextContent();
                return tc.items.map(it => ({ str: it.str, hasEOL: it.hasEOL }));
            }""",
            pdf_url,
        )
        print(f"\n{len(result)} text items in {target_file}:")
        for item in result:
            print(f"  {item['str']!r}  {'[EOL]' if item.get('hasEOL') else ''}")

        browser.close()


if __name__ == "__main__":
    main()
