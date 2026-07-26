#!/usr/bin/env python3
"""Dumps the raw pdf.js getTextContent() items for a given PDF page, to debug text-matching issues."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_URL = "http://127.0.0.1:5051"


def main():
    pdf_url = sys.argv[1]  # e.g. http://127.0.0.1:5051/session/<id>/pdf/record_06.pdf

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{APP_URL}/review")

        result = page.evaluate(
            """async (pdfUrl) => {
                const pdfjsLib = await import('/static/pdfjs/pdf.min.mjs');
                pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/pdfjs/pdf.worker.polyfill.mjs';
                const doc = await pdfjsLib.getDocument({ url: new URL(pdfUrl) }).promise;
                const page1 = await doc.getPage(1);
                const tc = await page1.getTextContent();
                return tc.items.map(it => ({ str: it.str, hasEOL: it.hasEOL }));
            }""",
            pdf_url,
        )
        for item in result:
            print(repr(item["str"]), "EOL" if item.get("hasEOL") else "")

        browser.close()


if __name__ == "__main__":
    main()
