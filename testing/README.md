# Automated browser testing

Playwright-driven verification that actually opens the web app in a real (headless) Chromium browser
and checks it end to end — not just the backend API in isolation. Set up specifically to verify the
PDF-highlighting feature, since that's a real rendering/layout behavior that curl-testing the backend
can't confirm.

## Setup (already done once, documented for reference)

```
python3 -m venv testing/.venv
testing/.venv/bin/pip install playwright
testing/.venv/bin/playwright install chromium
```

## Running it

**First, start the dedicated test server** (port 5051 — separate from the normal port 5050 a person
would actually use):

```
testing/start_test_server.sh
```

This matters: each analysis run deletes the *previous* session's extracted PDFs from disk (by
design — see `webapp/README.md`). If tests ran against the same port 5050 someone was actively using,
every test run would silently delete whatever session that person had open, breaking their in-progress
review. Port 5051 is a completely separate app instance/session directory so testing never touches a
live session.

**Then run the check:**

```
testing/.venv/bin/python testing/verify_highlighting.py [zip_path] [--headed]
```

Defaults to `sample_data/case_000_pdfs.zip` (the fast ~25s single-record test case) if no zip is
given. Pass `--headed` to watch it run in an actual visible browser window instead of headless.

## What it checks

1. Uploads the zip, waits for the full analysis to complete.
2. Clicks through every finding in the results list.
3. For findings **with** a quote: confirms a highlight box appears, and — critically — that it
   **closely matches** (within a few pixels) the actual bounding box of a real rendered text span
   from pdf.js's own `TextLayer` (not just "is near some text somewhere," an exact positional match).
4. For findings **without** a quote: confirms **no highlight box is showing at all** — this catches
   the "stale highlight from the previously-selected finding" bug class specifically.
5. Captures a screenshot of the viewer panel per finding to `testing/screenshots/` for visual
   inspection.
6. Fails on any browser console error or failed HTTP request (e.g., a 404 fetching a PDF).

Prints `PASS` or `FAIL` and exits with the matching status code.

## Known real bugs this already caught

- Werkzeug served a stale cached template after an HTML edit (`TEMPLATES_AUTO_RELOAD` wasn't set) —
  the DOM element the JS expected didn't exist, causing a null-reference crash on every finding click.
- Manual PDF-coordinate math (deriving highlight position from the raw PDF text transform matrix) was
  measurably wrong — replaced with rendering pdf.js's own `TextLayer` and measuring the real DOM spans
  via `getBoundingClientRect()`, which is what this test now verifies stays correct.
- A stale highlight from a previously-selected finding stayed on screen when a later-selected finding
  had no quote of its own, misleadingly appearing to support the wrong claim.
- The model occasionally wrote the literal string `"not stated"` into a `source_file` field (a
  required schema field it couldn't leave empty), which the frontend then tried to fetch as if it
  were a real filename, 404ing mid-render and skipping the highlight-clearing step. Fixed with both a
  tightened prompt instruction and a frontend `realValue()` filter that treats placeholder-looking
  strings as absent regardless of what the model outputs.

## Other verification scripts (same setup/test-server as above)

- `verify_edit_feature.py` — inline finding editing (Space to edit, Enter to save, edit persists and
  shows in the export).
- `verify_detail_slider.py` — the Brief/Standard/Detailed slider actually changes what's sent/returned.
- `verify_stale_session.py` — clicking a finding whose session PDFs were replaced by a newer upload
  shows a clean "session expired" message instead of a raw exception.
- `verify_layer_alignment.py` — canvas/text-layer/highlight-overlay position/size stay in sync across
  5 browser widths (700-1800px) plus a resize-after-render — the authoritative regression guard for
  the highlighting-alignment bug class specifically (rerun this first if highlighting looks off).
- `verify_case_creation.py` — Case Mode end to end: Complaint/NOI auto-detection + extraction
  (defendant names/DOL/facts), recursive ingestion of every case subfolder (not just `records/`),
  record_type/author/at_issue rendering, and the no-complaint-found fallback warning.
- `verify_docx_export_template.py` — the exported Word document matches the firm's `Blank
  Chronology Template.docx` structure exactly (header block, Abbreviations/Record Sources,
  Outstanding Records, the DATE/PAGE/RECORD/SOURCE/DESCRIPTION table), Times New Roman 12pt body
  text, checked via `python-docx`.
- `verify_bates_disambiguation.py` — deliberate "trap": a 2-page PDF with the IDENTICAL quoted
  sentence on both pages, each stamped with a different Bates number. Hand-crafts findings (via the
  sessionStorage restore trick, no LLM call needed) citing each page in turn, plus one citing a Bates
  number that exists on neither page. Confirms the viewer lands on whichever page's own stamp actually
  matches the finding's citation — not just the first textual match — and that the Bates-check banner
  never claims a false "match" when the cited Bates doesn't exist on the page shown.
- `verify_multicolumn_highlighting.py` — a 2-column medical-note layout (a common real-world record
  format) with overlapping vocabulary between columns. Confirms the highlight lands in the correct
  column (not the other one) by checking both pixel alignment to a real text span AND that the box's
  x-position is actually within the correct column's rendered range.
- `verify_repeated_boilerplate_disambiguation.py` — harder version of the Bates-disambiguation trap:
  a 5-page PDF where the same sentence is repeated verbatim on every page (templated EHR boilerplate).
  Confirms all 5 pages resolve correctly via the Bates cross-check alone, proving the disambiguation
  logic scales past just two candidates.
- `verify_export_confirm_modal.py` — confirms the "N findings haven't been reviewed" export warning
  is a styled in-app modal (`#export-confirm-modal`), not the browser's native `confirm()` dialog —
  asserts via a Playwright `dialog` handler that no native dialog ever fires, and that both Cancel
  and "Export Anyway" behave correctly.
- `verify_dashboard.py` — the new home screen (`/`): confirms "Start a New Case" is a large, visible
  CTA linking to `/case`, confirms real historical cases render from `/case/jobs` with the expected
  fields (plaintiff, status, document count), and confirms clicking "Continue reviewing" on a ready
  case actually opens `/review?case=...&group=...` and renders real findings, not just that the link
  exists.
- `verify_dashboard_edge_cases.py` — the dashboard branches the happy-path test above doesn't reach:
  the empty-state message (no cases yet), a `/case/jobs` fetch failure (must show a distinct
  "couldn't load" message, never silently render as if there were just no cases), a case whose
  primary group is ready but has a failed secondary group (must show both "Continue reviewing" AND
  a separate "View case status" link, not hide the failure), and an errored case with nothing to
  review yet (must show "View status", never "Continue reviewing"). Mocks `/case/jobs` via
  Playwright route interception — deterministic, no LLM call, doesn't depend on whatever real case
  history happens to exist on this machine.
- `verify_summary_edit.py` — the AI-drafted summary box at the bottom of the timeline is
  click-to-edit, same as an individual finding (`startEditingSummary` in app.js, mirroring
  `startEditingFinding`): click opens an inline textarea pre-filled with the current text, Enter
  commits, Escape cancels, the edit survives a page refresh (same sessionStorage pattern as review
  status/finding edits/added facts), and the edited text — not the original — is what actually ends
  up in the exported chronology.
- `verify_chronology_preview_and_case_ui.py` — three related chronology-builder UI changes: the
  "Preview Chronology" button (bottom of the timeline) renders exactly what the Word export would
  produce as HTML directly in the viewer pane (reusing `buildExportPayload()` — the same data
  `/export/docx` renders, so it can't drift out of sync), and clicking any finding's citation
  afterward exits preview mode automatically; the single-zip upload form is hidden entirely in
  Case Mode; the "Check for new files" control now lives on the review page itself (where a
  reviewer actually works), not just the separate `/case` status page.
- `verify_case_group_not_yet_created.py` — real bug found via live testing on case_smith: a
  reviewer who opens the review link the moment a case starts (the normal way to use this app) can
  have their very first poll land before the manifest's group entry is even created yet (Phase 1-3
  — Complaint/NOI detection + document grouping — can take well over a minute on a large case).
  `/case/<job_id>/<group_key>/results` used to return a hard 404 "Unknown group" for this
  completely normal, transient state; the frontend's poll loop treats any `error` field as fatal
  and never schedules another poll, silently freezing the page forever — even long after the job
  actually finished. This is what a real user's "no Bates numbers in the export" and "PDFs no
  longer on disk" reports turned out to be: a page that stopped updating at the very first poll,
  showing stale/empty data indefinitely. Confirms the fixed endpoint returns `{"ready": false, ...}`
  (200) while the job isn't done yet, still correctly hard-404s once the job IS done and the group
  genuinely never existed, and confirms via mocked responses that the frontend keeps polling across
  that transition and eventually renders the real data.
- `verify_case_highlighting_regression.py` — the strongest highlighting check in the suite: runs
  two full, real, multi-document Case Mode fixtures end to end (`case_ferreira`, `case_whitfield`
  — see `scripts/make_case_test_folders.py`, same 10-subfolder structure as `case_smith` but each
  with genuinely different plaintiff/defendant/facts/medical content, all Bates-stamped), then
  clicks through **every single citable finding in both cases** (not a sample) checking pixel
  alignment against a real text span AND that the Bates cross-check banner never shows "mismatch."
  Any misalignment or mismatch anywhere is a hard failure. Slow (~15-30 min for both cases).
- `verify_case_smith_live_view.py` — end-to-end reproduction using a real, full case_smith
  (17-document) run: opens the review page immediately (before the job finishes), leaves it open
  across the entire run, and confirms Bates numbers appear in the still-open tab, the PDF viewer
  loads a source document, and the exported `.docx`'s PAGE column has real values — all without
  ever reloading the tab. Slow (~15-25 minutes); a stronger, real-world companion to the faster,
  deterministic `verify_case_group_not_yet_created.py` above.
- `verify_case_job_deeplink.py` — confirms the dashboard's `/case?job=<job_id>` deep link actually
  works when opened in a browser tab that never itself started that job (the real scenario: clicking
  a historical case from a different tab/session than the one that originally started it). Starts a
  real (small, single-document) case directly via `POST /case/start`, then opens it in an
  independent browser context and confirms the right job's data loads via the URL param alone, not
  silently nothing.

**Note on routes:** the quick single-zip-upload/review flow (this file's original subject) now
lives at **`/review`**, not `/` — `/` is the dashboard (`dashboard.html`/`dashboard.js`), added
2026-07-24. Every script above that drives the upload form goes to `{APP_URL}/review` first.
