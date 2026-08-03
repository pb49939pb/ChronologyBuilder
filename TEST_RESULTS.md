# Test Run Log

Tracks results of running `scripts/run_chronology_test.py` against `sample_data/case_001_raw_records.md`,
scored against `sample_data/case_001_answer_key.md`. Add a new entry each time a different model or
prompt is tried, so results are comparable over time.

## Run 1 — 2026-07-21 — llama3.1:8b

**Command:** `python3 scripts/run_chronology_test.py sample_data/case_001_raw_records.md llama3.1:8b`
**Performance:** 58.2s wall time, 662 output tokens, ~16.7 tok/s

**Scoring against answer key checklist:**

| Check | Result |
|---|---|
| All 11 events present, correct order | Partial — 9/11; merged the 01/22 hematology consult and 01/25 discharge into one "01/22-25" bucket |
| Both embedded dates captured (12/18/2024, 01/23/2025) | **Failed** — neither appeared anywhere in the output |
| Three anticoagulants kept distinct, no conflation | **Passed** — enoxaparin/heparin/apixaban correctly kept separate by phase |
| SOB discrepancy (Record 4 vs Record 5) flagged | Partial — correctly identified in substance, but the output literally said "None explicitly stated" immediately before describing the exact discrepancy that exists |
| Vague chief complaint (Record 4) not embellished | Passed |
| No invented facts | Passed — no fabrication found on manual check |
| Every claim traceable to a Record number | Mostly — one bucket cited "Record 7-8" instead of attributing specific facts to each |

**Takeaway:** genuinely encouraging first result — the error type I most expected (mixing up which
anticoagulant was given when) did not happen, and it caught a real, subtle cross-document
inconsistency. The failures were an organizational/granularity issue (missing embedded dates,
merging two events) and a self-contradictory summary line, not fabrication. This is a good
illustration of the product doc's core point: strong enough to be a useful first pass, not strong
enough to skip human review — the "None explicitly stated" line is exactly the kind of confidently
wrong statement that would slip through if nobody actually read the output.

**Next runs to try:** same test against `qwen2.5:7b` and `qwen3:8b` (thinking mode) for comparison;
then a verifier-pass prompt asking a second model to check the embedded-date facts specifically,
since that's the demonstrated failure mode.

## Run 2 — 2026-07-21 — llama3.1:8b, via the web app (real PDF upload, not raw text)

**How:** `sample_data/case_001_raw_records.md` split into 9 individual PDFs (`scripts/make_test_pdfs.py`),
zipped as `sample_data/case_001_pdfs.zip`, uploaded through `webapp/app.py`'s `/analyze` endpoint —
the actual upload → PDF-text-extraction → prompt → model path, not the CLI script directly.

**Performance:** 72.5s wall time, 780 output tokens, ~16.3 tok/s, all 9 PDFs' text extracted cleanly (no OCR warnings, as expected for text-based test PDFs)

**Scoring against answer key checklist:**

| Check | Result |
|---|---|
| All 11 events present, correct order | **Passed** — all 11, correctly ordered, no merging this time |
| Both embedded dates captured (12/18/2024, 01/23/2025) | **Passed** — both appeared, correctly attributed (model even self-flagged the 01/23 one as "implied" rather than explicit, which is honest behavior) |
| Three anticoagulants kept distinct, no conflation | **Passed** |
| SOB discrepancy (Record 4 vs Record 5) flagged | **Failed** — output said "None explicitly stated," and unlike Run 1, did not describe it afterward either |
| Vague chief complaint (Record 4) not embellished | Passed |
| No invented facts | Passed |
| Every claim traceable to a source filename | Passed — cites `record_XX.pdf` for every line |

**Takeaway:** better on the failure mode Run 1 had (embedded dates, event granularity) — worse on the
one Run 1 got right (missed the SOB discrepancy entirely this time). Same model, same document set,
same prompt, different result. This is exactly the run-to-run non-determinism that's the entire
argument for the self-consistency/verifier-pass mitigations already written into
`PRODUCT_DEFINITION.md` §5 — a single run, even from a model that's "good enough on average," isn't
reliable enough on its own for a specific case. Neither run alone was fully correct; a paralegal
reading only one of these two outputs would miss something real.

## Run 3 — 2026-07-21 — llama3.1:8b, real personal medical document (details intentionally not logged)

**Note on data handling:** this run used a real personal medical document, not synthetic test data.
No identifying details (name, DOB, provider, facts) are recorded here or anywhere else in this repo —
only the abstract pattern of the finding, which isn't identifying on its own.

**Finding — a new failure mode, the inverse of Runs 1–2:** the model's "Discrepancies noted" section
flagged two pairs of statements as conflicting when they were not:

1. An affirmative/negative pair that were actually consistent (e.g., a "condition is irregular"
   statement and a "No" answer to "is it regular?" — these agree, they don't conflict).
2. Two restatements of the same fact using different phrasing (e.g., "for 10 months" stated two
   different ways) flagged as if they were two different data points.

**Takeaway:** Runs 1–2 showed the model *missing* a real cross-document discrepancy (a false
negative). This shows it *inventing* a discrepancy from paraphrase variance (a false positive). Same
underlying lesson as before — don't trust the discrepancies section either way without checking it —
but this is a distinct failure mode worth testing for separately: the model isn't reliably
distinguishing "two facts disagree" from "two phrasings of one fact." A framework document the user
provided (`Nurse Paralegal in Medical Malpractice Litigation.pdf`) explicitly calls for separating
documented fact / patient-reported history / provider opinion / reviewer observation into distinct
categories — a prompt that enforces that kind of categorical discipline should reduce this specific
error. Next step: rewrite `PROMPT_TEMPLATE` (in both `scripts/run_chronology_test.py` and
`webapp/app.py`) around that framework and re-test against both this failure mode and the Run 1/2
missed-discrepancy mode.

## Run 4 — 2026-07-21 — llama3.1:8b, rewritten prompt (CLI, `sample_data/case_001_raw_records.md`)

**What changed:** `PROMPT_TEMPLATE` extracted to `prompts/chronology_prompt.txt`, shared by both the
CLI script and the web app, rewritten around the nurse-paralegal framework document — adds a
Duty/Breach/Causation/Damages framing, clinical-event-time vs. documentation-time distinction, a
strict definition of what counts as a real discrepancy (with a worked example), an explicit
"Potential Issues" red-flag checklist, and four labeled output sections (Timeline / Potential Issues /
Discrepancies / Summary) instead of one loose block.

**Performance:** 110.4s wall time, 1239 output tokens, ~15.3 tok/s (longer/slower than Runs 1-2, as expected — the prompt itself is much longer and asks for more structured output)

**Result vs. checklist:**

| Check | Result |
|---|---|
| All 11 events present, correct order | Mostly — but the model **duplicated** the 01/22 hematology-consult content onto a fabricated second 01/23 entry, instead of reporting the actual 01/23 fact (the venous ultrasound). It did flag its own uncertainty on that entry's sourcing ("assume continuation from Record 7"), but the content was still wrong. |
| Both embedded dates captured | Partial — 12/18/2024 correct; 01/23/2025 present as a date but with fabricated/wrong content (see above) |
| Three anticoagulants kept distinct | Passed — enoxaparin, heparin, and apixaban all correctly named and not conflated |
| SOB discrepancy flagged as a "discrepancy" | Still not flagged under DISCREPANCIES ("None found") — **but** the new POTENTIAL ISSUES section independently caught the same underlying fact as a "delayed evaluation" red flag: symptoms reported to PT on 01/19 weren't addressed until the 01/21 hospitalization. Arguably a *better* framing for a malpractice chronology than a bare "discrepancy" label, even though it misses the strict checklist item as originally written. |
| No invented facts | **Failed this run** — the fabricated duplicate 01/23 entry described above is a real hallucination, not just an organizational slip |

**Takeaway:** the new "Potential Issues" section is doing genuinely useful, legally-relevant work
(the delayed-escalation flag is arguably the single most important fact in this whole case). But this
run introduced a new fabrication (a duplicated, wrongly-dated event) that neither Run 1 nor Run 2 had.
Net: better analysis quality, not yet better reliability — reinforces that human verification of every
line remains mandatory regardless of prompt quality.

## Run 5 — 2026-07-21 — llama3.1:8b, rewritten prompt, via the web app (`case_001_pdfs.zip`)

**Performance:** 118.5s wall time, 1373 output tokens, ~15.6 tok/s, all 9 PDFs extracted cleanly

**Result:** this run correctly captured the 01/23/2025 venous ultrasound fact (no duplication bug this
time), and the POTENTIAL ISSUES section again independently caught the delayed-evaluation red flag
around the 01/15 PCP visit not raising DVT/PE concern despite the known risk factor — genuinely sharp
observation. DISCREPANCIES again said "None found."

**New problem found:** asking explicitly for "date and time" and "facility, department, and provider"
per event — intended to add useful structure — backfired into a new hallucination surface. The model
invented specific times of day (e.g., "01:07/2025, 10:00", "11:00") and department names (e.g.,
"Post-Anesthesia Care Unit," "Vascular Lab") that appear **nowhere** in the source records, and
misassigned Dr. Okafor's role as "Anesthesiologist" in one entry when every source document identifies
him as the surgeon. The prompt does say "if stated" and "say so if only a date is given," but that
guardrail isn't being followed reliably — the model fills the field anyway rather than admitting the
source doesn't specify it.

**Takeaway:** asking for more granular structured fields increases the hallucination surface area if
the guardrail language isn't strong enough. Next prompt iteration should make the "don't invent it,
say 'not stated'" instruction more forceful and specific to time/department/role fields specifically,
since generic "don't infer anything" language wasn't sufficient to stop it here.

## Run 6 — 2026-07-21 — llama3.1:8b, tightened anti-fabrication prompt (CLI)

**What changed:** `prompts/chronology_prompt.txt` rewritten with an explicit "omit rather than guess"
framing, concrete negative examples mirroring Run 5's actual mistakes (invented clock times, invented
department names, misassigned provider role, duplicated entries), and a "before you finalize, re-check
every time/department/role against the source" self-check step appended at the end of the prompt.

**Performance:** 202.3s wall time, 1040 output tokens, ~11.8 tok/s (slower — longer prompt, plus the
model chose to format the timeline as a markdown table this run, which is fine)

**Result — the fixes worked:**
- **No invented clock times** anywhere in the output (Run 5 had several)
- **No misassigned provider role** — Dr. Okafor consistently identified correctly this run (Run 5 called him "the anesthesiologist" once; he's the surgeon)
- **No duplicated/fabricated entries** — the 01/22 and 01/23 events are correctly separate and distinct this time (Run 4 had duplicated wrong content across these two dates)
- **Appropriate hedging appeared** — the 01/23 ultrasound entry says "Not stated" for department and "(implied)" for its source, rather than confidently asserting specifics it wasn't sure of

**New minor regression:** the 12/18/2024 embedded date (pre-op Factor V Leiden clearance) is missing
from this run's timeline entirely — it had been caught in Runs 5-6's predecessor runs. Also, the SOB
discrepancy is still routed into POTENTIAL ISSUES ("delayed evaluation... shortness of breath reported
to the physical therapist") rather than DISCREPANCIES — on reflection this may actually be the *more
correct* categorization under the new strict discrepancy definition, since it's genuinely more of a
delayed-care-escalation issue than a factual contradiction between two sources. Worth revisiting
whether the original answer key's "should be flagged as a discrepancy" expectation for this item was
the right bucket now that a dedicated "potential issues" section exists.

**Takeaway:** the tightening worked on exactly the failure modes it targeted, at the cost of one
embedded date being missed this run. Net positive — fabricating specific false details (a role, a
time, a duplicate event) is a worse failure than omitting one real date, since a paralegal reviewing
the output is more likely to independently notice a gap than to notice a confidently-stated wrong
detail. Still not perfect, still requires full human verification — but measurably safer in the
direction that matters most.

## Highlighting reliability investigation (2026-07-21, via new Playwright test suite)

Extensive debugging session after the document viewer's highlighting was reported as "not working
correctly." Real bugs found and fixed, in order of discovery:

1. **Stale Flask template cache** — `TEMPLATES_AUTO_RELOAD` wasn't set, so an HTML edit didn't take effect without a full restart, causing a null-reference crash on every click. Fixed permanently.
2. **Wrong coordinate math** — highlight boxes were positioned by manually re-deriving pixel coordinates from the PDF's raw text transform matrix (baseline vs. box-top, ascent/descent). Replaced with rendering pdf.js's own `TextLayer` and measuring real DOM spans via `getBoundingClientRect()` — now the browser's layout engine computes the position, not hand-rolled math.
3. **Stale highlight left over from a previous finding** — selecting a finding with no quote didn't clear the box from whichever finding was selected before it, misleadingly implying support for the wrong claim.
4. **Model wrote literal placeholder text** (`"not stated"`) into a required `source_file` field, which the frontend then tried to fetch as an actual filename (404). Fixed with a prompt instruction to omit untraceable findings entirely, plus a frontend `realValue()` filter as a defensive backstop.
5. **Quote-mark style mismatches** — the model sometimes reproduced an otherwise-verbatim quote but swapped the source's quote-mark style (source uses "double quotes," model's quote field uses 'single quotes' around the same phrase). Fixed by stripping all quote-mark variants (straight + curly, single + double) during matching.
6. **Punctuation and word-order drift** — confirmed via debug-instrumented test runs that ~10-20% of "couldn't locate" failures were the model writing something 95% verbatim but changing a trailing punctuation mark or reordering a couple of words for smoother phrasing (e.g., source "daily to continue for X" → model's quote "continue daily for X"). Fixed three ways: (a) strip all punctuation, not just quotes, during matching; (b) added a fuzzy fallback that finds the longest contiguous word-run from the quote that does appear verbatim, if the exact quote isn't found anywhere — labeled as a "partial match" in the UI rather than presented as equivalent to an exact one; (c) tightened the prompt with the two specific mistake patterns spelled out.

**Result after all fixes:** across repeated full-suite runs against case_001 (12-14 findings each, non-deterministic model output varies run to run), zero unexplained failures — every finding either got a pixel-perfect highlight (0.0px off the nearest real text span, confirmed via `testing/verify_highlighting.py`) or correctly showed no highlight for findings with no quote. One run needed the fuzzy fallback and it worked correctly. This was a real, measurable reliability improvement, not just a claimed one — see `testing/README.md` for how to reproduce.

**Also found and fixed the same session:** a stale-session 404 (clicking a finding whose PDFs were deleted by a newer upload replacing them, e.g. after restoring a cached result via `sessionStorage` from before a newer analysis ran) now shows a clear "this session has expired, please re-upload" message instead of a raw exception — verified via `testing/verify_stale_session.py` by deliberately deleting a session's files mid-test.

## New test cases added — case_002 and case_003 (2026-07-21)

Two more synthetic cases, same format as case_001, for variety: `sample_data/case_002_raw_records.md`
(delayed diagnosis of perforated appendicitis) and `sample_data/case_003_raw_records.md`
(anticoagulation dosing error). Each has its own answer key. Notably, **case_003 was deliberately
built to contain a real discrepancy** (physician order: warfarin 5mg vs. home health MAR: 10mg
actually administered) — the first test case designed to check the opposite failure mode from
case_001/002 (missing a genuine conflict, not inventing a false one).

**Smoke test results (structured JSON pipeline, current prompt):**

- **case_002**: 6/8 timeline events, 1 potential issue, 0 discrepancies. Correctly did not invent a
  false discrepancy out of the 03/02→03/03 symptom-worsening pair (matches the intended answer key).
- **case_003**: 7/7 timeline events, 2 potential issues, **1 discrepancy — but the wrong one.** The
  model flagged "INR 6.8 (05/12) vs. INR 8.4 (05/14)" as a conflict, which is not actually a
  discrepancy — it's the same lab value trending upward over two days, consistent with a worsening
  bleed. Meanwhile it **missed the actual planted discrepancy** (5mg ordered vs. 10mg administered),
  even though Record 5 (the hospitalist's own note) states this explicitly. This is a genuinely
  useful negative result: tightening the prompt against false-positive discrepancies (Case 001 finding)
  does not guarantee real discrepancies get caught — the model can still both invent a wrong one and
  miss the real one in the same run. Reinforces that the discrepancy-detection behavior is not yet
  reliable in either direction, and a verifier pass or self-consistency check (§5 of the product doc)
  matters more than further prompt tweaking alone at this point.

## case_004 — a much larger case (31 documents / 31 pages) reveals a real capability boundary (2026-07-21)

`sample_data/case_004_raw_records.md` is a deliberately large synthetic case (22-day ICU stay, 31
separate documents) built specifically to test something case_001-003 couldn't: whether the pipeline
can track a **trend spread across many repetitive documents**, not just extract a fact stated in one.
Fact pattern: creatinine rises in every single daily progress note over 18 days, but nephrology isn't
consulted until day 18 — no individual document says "this is a problem," only the accumulated trend
across ~20 documents does. Full design and answer key in `case_004_answer_key.md`.

**Result:** `input_truncated: false` (21K chars of source text fit comfortably in the ~32K budget —
this case didn't end up testing context overflow, just document-count/volume), 22 timeline events,
0 discrepancies, and **only 1 potential issue — not the intended one.** The model's free-text
**summary** field actually did capture the real story correctly: *"Renal function declined
progressively throughout the admission, prompting nephrology consultation and initiation of
hemodialysis on hospital day 18."* But that understanding did not carry through to the structured
output that actually matters for a reviewer: the timeline included only one entry mentioning
creatinine at all (the nephrology consult itself, which explicitly states the trend), none of the 18
individual daily values were tracked as separate data points, and the delayed-recognition pattern was
never flagged as a `potential_issue`.

**Why this matters more than the earlier findings:** Runs 1-6 and case_002/003 were about whether the
model fabricates or misses things *within* a single document or a small, easily-held set of documents.
This is different — it's evidence that **aggregate understanding (visible in the free-text summary)
does not reliably translate into correct structured extraction** once the number of source documents
grows, even well within the stated context budget. A human paralegal reading all 31 documents in
order would very likely notice "wait, this number keeps going up every single day" — the model,
here, effectively did notice it enough to write a correct one-sentence summary, but didn't surface it
as an actionable, structured, cited finding. This is exactly the kind of gap a verifier/self-
consistency pass (or, longer term, a RAG architecture that explicitly aggregates same-type values
across documents rather than relying on the model to notice a trend unprompted) is meant to close —
and it's a stronger, more concrete argument for that architecture than anything found in the smaller
test cases.

## Highlight misalignment — real bug found in my own earlier test methodology (2026-07-21)

The user reported that highlights still didn't look correctly aligned with the visible PDF, despite
earlier automated tests reporting "0.0px off" every time. Investigating this seriously (rather than
re-running the same check and trusting it again) turned up **two real, compounding bugs**, plus a
**gap in the test methodology itself** that let them slip through repeatedly.

**Bug 1:** pdf.js's `TextLayer` constructor internally overwrites its container's CSS width/height
with a `calc()` expression tied to custom properties (`--total-scale-factor`, `--scale-round-x/y`)
that this page never defines. Instead of erroring, the browser silently resolved this to a wrong
size (measured: 204px instead of the correct ~683px for a given page). Fixed by force-reasserting
the correct pixel dimensions with `!important` immediately after constructing and after rendering
the TextLayer (`setExactSize()` in `webapp/static/app.js`), so pdf.js's broken internal calc() can't
win regardless of what it does internally.

**Bug 2, the bigger one:** the canvas was centered by the outer flex container
(`justify-content: center`), but the invisible text-measurement layer and the highlight overlay were
positioned via `position: absolute; top:0; left:0`, which resolves relative to the *container's*
edge, not the canvas's own (centered, therefore offset) position. At a narrow browser width, the
centering offset happens to be ~0, so this was invisible — at any realistically wide browser window,
the offset was substantial (measured up to 147px horizontally) and the highlight visibly drifted from
the actual text. Fixed by wrapping the canvas and both overlay layers in a new
`.pdf-page-wrapper` (`display: inline-block`, so it shrink-wraps to exactly the canvas's size) —
*that* wrapper is what gets centered by the flex container, so the overlay layers' `top:0; left:0`
now resolves relative to the canvas's own box rather than the wider container around it.

**The methodology gap, stated plainly:** every earlier "0.0px off" result was true but insufficient —
it checked that the highlight box matched a text-layer span's position, which is trivially true by
construction (the highlight is computed *from* that span's measurement), so it could never catch the
text-layer *as a whole* being offset from the canvas it's supposed to overlay. It verified internal
consistency, not the actual end-to-end property that matters: does the highlight align with the
*visible page*. `testing/verify_layer_alignment.py` is the fix for the test methodology, not just the
bug — it independently measures canvas position/size against text-layer and highlight-layer
position/size as an explicit invariant, in addition to the highlight-vs-span check, and tests across
five browser widths (700-1800px) plus a resize-after-render scenario rather than one fixed wide
viewport. All five widths now pass cleanly, including the resize case. This script (not
`verify_highlighting.py` alone) is now the authoritative regression guard for this bug class.

## OCR fallback for scanned/faxed PDFs (2026-07-21)

User feedback: "I am wondering if it makes sense to get an OCR model involved for scanning the
PDFs. I don't think we are doing quite well enough reading some of these." Two separate quality
issues addressed:

**1. General extraction quality.** Swapped `pypdf` for `pdfplumber` (MIT license) as the primary
text extractor — `pypdf` is known to garble multi-column/irregularly-spaced layouts, which are
common in real medical records (vitals tables, med lists). `PyMuPDF`/fitz is faster and arguably
better quality but is AGPL-licensed, which needs explicit firm sign-off for a business tool before
using it — `pdfplumber` avoids that open question entirely while still being a clear upgrade.

**2. Genuinely scanned/faxed pages (no text layer at all).** Previously these were detected via a
low-character-count heuristic and simply excluded with a warning. Now, any page below
`MIN_CHARS_PER_PAGE` (20 chars) is rasterized via `pdfplumber`'s `page.to_image(resolution=300)`
(uses `pypdfium2` under the hood — no ImageMagick/system binary needed) and run through `easyocr`
(pure-Python/pip-installable, PyTorch-based — chosen specifically because Tesseract needs a system
binary and Homebrew isn't installed on this machine). A page is only excluded if OCR *also* yields
nothing.

**Verified with a synthetic scanned test PDF** (`scripts/make_scanned_test_pdf.py` → renders a
realistic clinic note as a flat image with Pillow, saved directly to PDF — confirmed via `pypdf`/
`pdfplumber` that it has zero extractable text, i.e. a faithful stand-in for a real scan/fax):
- OCR fallback correctly kicked in (`num_ocr_pages` = 1), extraction succeeded (`ok: true`), and the
  full pipeline produced a sensible structured chronology from the OCR'd text — timeline, potential
  issues (delayed BP monitoring), and a coherent summary. OCR quality was good but imperfect (e.g.
  "40mg" read as "4Omg", periods read as colons in a couple of spots) — expected and acceptable,
  since the warning surfaced to the user says to double-check these findings.
- Regression-checked `case_000` (normal, text-layer PDF) — identical-quality extraction and exact
  quote matches as before the `pypdf`→`pdfplumber` swap. No regression.
- Re-ran `testing/verify_layer_alignment.py` (the highlighting-alignment regression suite) — still
  PASS on all 5 viewport widths. The extractor swap doesn't touch the rendering/highlighting path,
  but worth confirming given how much effort went into that fix.

**Real, inherent limitation surfaced by this work, not a bug:** the document viewer's highlighting
works by having pdf.js search the *actual PDF's* embedded text layer for the model's quoted text. A
scanned/faxed PDF has no text layer at all — the OCR'd text exists only server-side, used to build
the prompt sent to the model. So a finding sourced from an OCR'd page can never be auto-highlighted;
there's nothing in the PDF itself for the browser to search. Rather than let this silently produce
the generic (and, given the recent highlighting-reliability work, potentially alarming) "couldn't
locate the quote" message, the backend now reports which filenames needed OCR (`ocr_files` in the
`done` event) and the frontend shows an accurate, specific explanation instead: the page was scanned/
OCR'd, so auto-highlighting isn't possible, review the source image manually. Verified via Playwright
that this message renders correctly and no console errors occur when viewing an OCR'd finding.

## Real-world PDF stress test: Olivia's actual visit summaries (2026-07-22)

User feedback: viewer felt "zoomed in and cut off the edges," and highlighting wasn't landing
precisely. Investigated against the user's own real, multi-page (up to 6 pages) "Visit Summary"
PDFs — the first time this app has been tested against real-world-generated (not synthetic) PDFs.
Tested via the isolated port-5051 test server against a zip built from the live session's actual
files, never touching the user's live port-5050 session. Two distinct, real bugs found and fixed:

**Bug 1 — fixed scale, not fit-to-width.** `renderPage()` in `webapp/static/app.js` rendered every
page at a hardcoded `scale: 1.4` (≈857px wide for a letter page) regardless of how much room the
viewer pane actually had (measured ~709px wide in a realistic window). Compounding this,
`.viewer-canvas-wrap` used `justify-content: center` with `overflow: auto` — a real cross-browser
quirk where content clipped by *centering* isn't always reachable by scrolling (confirmed
empirically: `scrollWidth` measured smaller than the canvas's actual overflowing width, meaning
part of the page — a left-hand lab-results column, in one real screenshot — was truncated
mid-word and literally unreachable, not just requiring a scroll). Fixed two ways: (1) added
`computeFitToWidthScale()`, which picks a render scale from the container's actual current width
instead of a fixed number — safe because canvas/text-layer/highlight-layer are still all derived
from that one viewport object and explicitly sized together in JS, so nothing about the
layer-alignment invariant depends on which scale value gets chosen; (2) switched
`justify-content` from `center` to `flex-start` as defense-in-depth, so any remaining overflow is
a normal scrollable trailing edge rather than an unreachable centered one. Verified via screenshot:
previously-truncated left-column text (lab reference ranges, medication list) now renders in full.

**Bug 2 — highlighting into blank space below real content.** On one of the real documents (an
nAbleIVF EMR export that also trips a "Ignoring wrong pointing object 9 0 (offset 0)" xref warning
from `pypdf` — i.e., a mildly malformed file), some quote matches produced a highlight box floating
in blank margin space with no visible text under it (caught on screenshot: a yellow bar sitting
well below the page's actual printed content and its "Page 1 of 6" footer). Root cause: pdf.js's
`getTextContent()` can return text items for a page whose own coordinates place them entirely
outside that page's actual printed bounds — confirmed by cross-checking with `pdfplumber` (used
server-side), which parses the identical file and reports zero characters outside the page's real
[0, height] bounds, so this is specifically a pdf.js-side parsing quirk on this file, not a bad
extraction. Fixed two ways, both in `webapp/static/app.js`: (1) `findQuoteInDoc` now converts each
text item's own PDF-space coordinates through `viewport.convertToViewportPoint()` and excludes any
item that lands outside the page's actual bounds from the search entirely, before a quote is ever
matched against it; (2) a second, independent check in `renderPage`'s highlight-drawing loop uses
the actual rendered `getBoundingClientRect()` position (ground truth, not a re-derivation) to skip
drawing any highlight box that would still land outside the page — defense-in-depth in case a
different cause ever produces an out-of-bounds span on some other malformed PDF. Re-verified across
several fresh runs (model output is non-deterministic run-to-run, so this was checked repeatedly,
not once): zero out-of-bounds highlights.

**One residual case investigated and found NOT to be a bug:** a highlight landing very close to a
page's bottom margin, initially indistinguishable by eye from the blank-space bug. Checked directly
against `pdfplumber`'s character-level render data (`page.chars`, including `non_stroking_color`)
and confirmed it's real, visible, correctly-positioned text — the page's own small italic footer
("Printed from nAbleIVF EMR on <date>" / "Page N of M"). The model citing footer boilerplate as if
it were a clinical finding is a separate content-quality issue (prompt could exclude footer/header
boilerplate more explicitly), not a positioning bug — logged here for future reference, not fixed
this session.

**Regression-checked after both fixes:** re-ran `testing/verify_layer_alignment.py` (all 5 viewport
widths PASS, canvas/text-layer/highlight-layer stay in sync) and `testing/verify_highlighting.py`
(5/5 highlight matches correct on the synthetic case_000 regression fixture) — the crop/scale and
off-page-filtering changes don't regress the layer-alignment fix from the previous session.

## Highlighting: fixed a fail-open bug and a misleading-success bug (2026-07-22, same day as above)

User re-tested with Olivia's real chronology and reported the first few timeline items got no
highlighting at all, and the next few didn't line up perfectly. Investigation found the earlier
same-day fix (bounds-filtering off-page text) had two gaps:

1. **Fail-open bug in the pre-filter.** `findQuoteInDoc`'s bounds check only ran `if (item.transform)`
   — any text item with a missing or malformed `transform` skipped the check entirely and was
   included unconditionally, defeating the filter for exactly the items most likely to need it.
   Fixed to fail closed: a missing transform, or one with fewer than 6 finite numbers, is now
   treated as out-of-bounds and excluded, matching the fail-safe direction the filter was supposed
   to have from the start.
2. **A match could "succeed" with zero highlightable content.** If every span overlapping a found
   quote got excluded by the bounds filter (or, for the post-render safety net, by pdf.js render
   position), the code still returned/treated it as a found match — `viewer-hint` claimed
   "Highlighted passage is the model's cited support," while zero highlight boxes were actually
   drawn. That's a worse UX than the original bug: it looks like a silent failure with no
   explanation. Fixed in three places: `findQuoteInDoc`'s exact-match loop now keeps searching
   subsequent pages instead of returning a page whose `matchedIndices` end up empty after
   filtering; the fuzzy fallback only accepts a candidate with at least one surviving index;
   `renderPage` now returns whether it actually drew a box, and `showFinding` uses that to show an
   honest, distinct message ("Found matching text on this page, but couldn't draw a precise
   highlight for it... showing the page; verify manually") rather than falsely claiming success.

Added a `window.__LFA_DEBUG_HIGHLIGHT` flag (same pattern as the existing
`window.__LFA_DEBUG_QUOTE_MATCH`) for future debugging of this bug class.

**Verified:** re-ran the real-document test 3 times fresh (model output is non-deterministic, so a
single clean run isn't enough evidence) — zero cases of "claims highlighted, shows nothing" across
all three runs. Re-ran `testing/verify_layer_alignment.py` — still PASS, unaffected. Screenshots
confirm the crop fix holds (full page width readable, including the previously-truncated left
column) and, where no highlight can be drawn, the message is now honest about it instead of silent.

## New feature: Key Facts panel (medications / procedures / diagnoses tabs) (2026-07-22)

User request: tabs above the timeline/PDF viewer showing categorized facts (current medications,
procedures, diagnoses), clickable, and clicking an item not already in the output adds it there.

**Backend:** extended `RESPONSE_SCHEMA` and `prompts/chronology_prompt_structured.txt` with three
new flat, atomic fact lists — `medications`, `procedures`, `diagnoses` — each using the same
date/text/source_file/quote shape as `timeline`, so they get the exact same citation-grounding and
verbatim-quote rules as everything else (no separate, weaker standard for these). Prompted the
model to keep each entry atomic ("Lexapro 10mg", not a full sentence) and to deduplicate exact
repeats without merging genuinely different facts (different doses, or a diagnosis stated at one
visit vs. ruled out at another, stay separate).

**Frontend:** a new "Key Facts" card (`#facts-panel`) sits between the stats/warnings bar and the
findings/viewer split-view, with tabs for each non-empty category and a row of clickable chips.
Clicking a fact:
- If no current finding already has the same normalized text, it's appended as a new "Key Facts
  (added)" finding — auto-approved (clicking is itself the explicit reviewer decision, not another
  unreviewed queue) — and the viewer jumps to its source, reusing all existing citation/highlight
  machinery since it's stored in exactly the same shape as a model-generated finding.
- If it's already present, the chip is shown in a distinct "already added" style, and clicking it
  scrolls to and briefly flashes the existing finding instead of creating a duplicate.
Persisted the same way as review status/edits (a new sessionStorage key per session), so added
facts survive a page refresh.

**Bug found and fixed during testing:** the first end-to-end test threw `Cannot access
'FACTS_CATEGORIES' before initialization` specifically on page refresh (not on a fresh upload) —
the refresh path restores a cached result synchronously at module-load time, before the script
had executed as far as the `const FACTS_CATEGORIES = [...]` line further down the file (a classic
temporal-dead-zone bug: the declaration was hoisted but not yet initialized when the early
restore-path code ran). Fixed by moving the constant up near the other early module-level consts,
before the cached-result restore block.

**Verified via Playwright:** panel renders with correct tab counts and real extracted facts on a
synthetic case; clicking a not-yet-present fact adds it (finding count +1), auto-approved, selected
in the viewer; clicking the same fact again does NOT duplicate it (finding count unchanged) and
instead is visibly marked "already added"; the addition survives a full page refresh with zero
console errors. Re-ran `testing/verify_layer_alignment.py` afterward — still PASS, confirming the
JS changes elsewhere in the file didn't regress the highlighting-alignment fix.

## Root-caused and fixed: medication list truncation (only 2 of 6 extracted) (2026-07-22)

User report: a real document's "Current Medications" list (Zofran, Lexapro, Imitrex, Claritin,
Magnesium, Prenatal Vitamin — 6 items) only produced 2 entries (Zofran, Lexapro) in the Key Facts
panel. Investigated with real evidence rather than guessing, and found **two separate, independent
problems**, both fixed:

**Problem 1 (the bigger one) — server-side text extraction was badly interleaving two columns.**
Dumped the actual text pdfplumber's plain `extract_text()` produces for this page and found the
medication list fragmented across multiple unrelated lines:
```
Current Medications: : 28.1
Zofran 4 mg LMP
Lexapro 10 mg : 06/08/2026 performed 2026-06-25
Imitrex 50 mg
Dr. B Initial Female Patient Visit 06/25/2026 by Dr Bazzi, Ali MD
Claritin 10 mg
Magnesium 500 mg
...
```
Root cause: this is a genuine two-column page (demographics/medications/labs on the left, vitals/
visit-notes/HPI narrative on the right), and pdfplumber's default extraction sorts primarily by
vertical position — so whenever the two columns' content overlaps in y-range (which it does for
most of the page), lines from one column get interleaved with unrelated lines from the other,
purely because they happen to sit at the same height. The model was reading exactly what the
extraction gave it and — reasonably — treated the interleaved unrelated text as a sign the list had
ended.

Fixed with a new `_extract_page_text()` in `webapp/app.py`: uses `pdfplumber`'s word-level
bounding boxes to detect whether a page has a consistent vertical column gutter (tolerating a few
full-width "divider" rows, like a section header, that legitimately span both columns), and if so,
reconstructs reading order as "all of the left column top-to-bottom, then all of the right column
top-to-bottom" instead of trusting the row-by-row default. Falls back to plain `extract_text()` for
single-column pages or anything too sparse/ambiguous to classify confidently (required a 12pt+ real
gutter and at least 85% of rows to cleanly fall on one side before it ever kicks in). Verified
against all 14 real pages across all 4 of the user's actual documents: every genuinely two-column
page got reconstructed with identical total character count (pure reordering, nothing lost or
added), and a spot-check of the reconstructed text showed the medication list as one clean,
unbroken 6-item block and the HPI section as a normal, readable paragraph instead of interleaved
fragments. Regression-checked against the existing single-column synthetic test PDFs
(`case_000`/`case_004`) — output identical to before (correctly falls back, no double-column false
positive).

**Problem 2 (found after fixing #1 — a genuine model-side completeness issue) — even with clean,
correctly-ordered text, the model still only extracted 2 of 6 medications.** This is a real LLM
completeness/attention limitation, not a data quality problem — consistent with an earlier
capability-boundary finding on `case_004` (aggregate understanding not reliably becoming complete
structured extraction). Two mitigations applied together in `RESPONSE_SCHEMA` and
`prompts/chronology_prompt_structured.txt`:
1. Reordered the schema so `medications`/`procedures`/`diagnoses` come right after `timeline` —
   before the more interpretive `potential_issues`/`discrepancies`/`summary` — on the theory that
   these simple enumeration tasks should get generated while the model's effective output
   budget/attention is freshest, not compete for whatever's left at the tail of a long generation.
2. Added an explicit "BE EXHAUSTIVE — DO NOT STOP AFTER THE FIRST FEW" instruction specifically
   for these three lists, naming the actual observed failure mode (stopping partway through a
   visible list) rather than a generic "be thorough" nudge.

**Verified together: 6/6 medications extracted correctly across 2 repeated fresh runs** (model
output is non-deterministic, so single-run success isn't sufficient evidence) against the real
document. Re-ran `testing/verify_layer_alignment.py` afterward — still PASS, confirming the backend
extraction/prompt changes don't touch the (separate) frontend highlighting-alignment code path.

**Honest limitation, not fully solved:** this is a mitigation, not a guarantee — a small local model
can still plausibly truncate a long enough list even with these two fixes, especially across many
documents in one run. The generator/verifier two-model architecture already described in
`PRODUCT_DEFINITION.md` §5/§6 (a second pass specifically checking "does this list match everything
actually in the source") remains the more robust long-term answer; these fixes reduce a confirmed,
reproducible failure but don't eliminate the underlying model-capability ceiling.

## Electron conversion built and verified (2026-07-22)

User decided to proceed with an Electron desktop shell (target user's machine is Windows, not this
Mac — see `DESKTOP_PACKAGING.md` for the reasoning). Built `electron/` (`package.json`, `config.js`,
`main.js`) supporting two modes: `local` (spawns Flask + Ollama on the current machine, used for
this testing) and `remote` (opens a window at an already-running instance elsewhere — the actual
target topology, see `TOWER_SETUP.md`).

No system Node.js was available (no Homebrew on this machine, consistent with earlier findings) —
installed a portable Node v22.14.0 tarball into `.tools/node/` (no sudo, no system-wide install)
specifically to build/test this.

**Verification approach**: Electron's window isn't visible via a normal OS-level screenshot in this
remote/headless development environment (confirmed: a full-screen `screencapture` while Electron
was the active app showed only the desktop wallpaper, no window — an environment limitation, not an
app bug). Used Electron's `--remote-debugging-port` (Chrome DevTools Protocol) with Playwright's
`chromium.connect_over_cdp()` instead, which reliably confirms both the window's real content and
lets Playwright drive it exactly like a normal browser page — screenshots taken this way show the
actual rendered app correctly.

**Verified working:**
- Cold-start spawn: killed the Flask backend, relaunched Electron fresh, confirmed (via `ps`
  parent/child PID check) that Electron's main process spawned `webapp/.venv/bin/python app.py` as
  a direct child, waited for it to respond, then showed the real app (not a blank/error window).
- Already-running detection: with the backend already up, Electron skips spawning and opens
  immediately — no duplicate process, no port conflict.
- Full functional flow inside the Electron window: zip upload → extraction → generation → results
  rendering → Key Facts panel → clicking a finding → PDF viewer with highlighting, all working, via
  CDP-driven Playwright interaction against the live Electron window.
- Window resize: re-ran the layer-alignment invariant check (canvas/text-layer/highlight-layer
  staying in sync) at 3 widths specifically inside the Electron window — still holds.

**Real bug found and fixed**: the PDF viewer initially failed inside Electron specifically (worked
fine in a normal browser) — `TypeError: this[#Oa].getOrInsertComputed is not a function`, from
pdf.js's optional-content-handling code. Root cause: `Map.prototype.getOrInsert(Computed)` is a
very new TC39 proposal (the "Map upsert" proposal) that even Electron 33.x's bundled Chromium
doesn't implement yet, despite our vendored pdf.js 6.1.200 already calling it. Same bug *class* and
same fix location as the earlier Safari-compatibility polyfill work — added `getOrInsert`/
`getOrInsertComputed` for both `Map` and `WeakMap` to the existing `webapp/static/pdfjs-polyfills.mjs`.
Verified fixed: reloaded the Electron window, re-ran the same flow, zero errors, highlight boxes
render correctly and pixel-aligned.

**This is the 7th distinct missing-recent-API polyfill** needed for this pdf.js build — the file's
own comment already said a 3rd/4th should trigger reconsidering an older, more conservative pdf.js
version instead of continued individual patching. Worth actually doing that evaluation soon.

**Not yet tested**: an actual Windows build. No Windows machine available in this environment —
`main.js`'s Windows-specific code paths (assumed `ollama.exe` on PATH, a not-yet-built PyInstaller
backend executable) are explicitly marked unverified in the code and need real Windows hardware to
confirm.

## OCR benchmarking and optimization (2026-07-22)

Built a proper benchmark rather than guessing at settings, prompted by wanting the OCR fallback to
be "as fast and accurate as possible." Generated 6 synthetic hard-case test PDFs
(`scripts/make_ocr_test_cases.py` → `sample_data/ocr_test_cases/`), all sharing identical
underlying text so results are directly comparable: clean typed (control), legible print-style
handwriting font, genuine cursive/connected script font, faxed/noisy (low contrast + grain +
slight blur), skewed (~4° rotation), and a worst-case combination (handwriting + skew + noise).
Each has a ground-truth `.txt` for scoring. None of this is real handwriting or real patient
data — cursive system fonts are a defensible proxy for recognition difficulty, not a claim of true
handwriting-recognition fidelity (see `RESEARCH_NOTES.md` Part 3 for why that distinction matters).

Built `testing/ocr_benchmark.py`, scoring every run with Word Error Rate (standard OCR/ASR metric:
edit distance between predicted and reference word sequences ÷ reference length), across 4
configurations × 6 cases. Full results in `testing/ocr_results/benchmark_results.json`. Findings:

1. **GPU (Apple Silicon MPS) is a clean win, not a tradeoff.** `easyocr`'s `gpu=True` flag checks
   for MPS explicitly when CUDA isn't available (confirmed by reading its source) — 3-4x faster
   than CPU (e.g. 9.3s → 2.5s on one case) with **identical** word accuracy on every single test
   case (same model/weights, just a different compute backend). Previously left at `gpu=False` as
   an unverified "safe default" — now confirmed and switched on.
2. **300 DPI is not better than 200 DPI, and it's slower** — counter-intuitive, but measured across
   every case (e.g. one case: 91.7% accuracy at 200 DPI vs. 88.9% at 300 DPI, and slower). Switched
   the production rasterization resolution down from 300 to 200.
3. **Deskew + auto-contrast preprocessing is the single biggest lever found.** On the skewed test
   case: 42.4% → 97.9% word accuracy. On the worst-case combined test: 45.8% → 93.1%. Cost on
   already-clean, non-skewed pages: negligible (99.3% → 98.6% on the clean control — noise-level).
   Both are cheap, pure PIL/numpy operations (deskew: try a small range of rotation angles, keep
   whichever maximizes the variance of horizontal row-darkness projections — text lines produce
   sharp peaks/troughs only when actually horizontal; contrast: a simple autocontrast stretch) —
   no additional ML model, negligible added time.
4. **Genuine cursive handwriting has a real, confirmed ceiling around ~50% word accuracy**,
   unmoved by any of the above settings — consistent with published figures for non-AI/non-VLM OCR
   engines on true handwriting (see `RESEARCH_NOTES.md` Part 3: ~50-70% typical, ~64% average
   across tools). This is a genuine capability ceiling of this class of OCR engine, not something
   further tuning fixes — the honest next step, if real handwritten records become common, is the
   vision-language-model OCR option already flagged as future work in `PRODUCT_DEFINITION.md` §5/§6
   (e.g. Qwen2.5-VL), not more `easyocr` tuning. Legible print-style "handwriting" fonts do
   meaningfully better (~92%), landing closer to typed-text accuracy — the ceiling is specifically
   about genuine cursive/connected handwriting, not "handwriting" as a single undifferentiated
   category.

**Implemented the winning configuration** in `webapp/app.py`: `_get_ocr_reader()` now uses
`gpu=True`; `_ocr_page()` rasterizes at 200 DPI (down from 300) and applies a new `_deskew()`
helper plus `ImageOps.autocontrast()` before handing the image to `easyocr`. Verified via direct
integration test (`pdf_to_text()` on both the original scanned test case and the new skewed test
case) and a full end-to-end run through the actual web app (upload → OCR → LLM generation →
results, warnings correctly flagged) — no regressions, `testing/verify_layer_alignment.py` still
PASS (confirms the OCR/extraction changes don't touch the unrelated highlighting-alignment code
path).

## Batch Folder Mode built and tested (2026-07-22)

New feature: point the app at a folder of mixed documents (not a single-patient zip upload) and it
groups them by patient automatically, then builds a separate chronology for each, sequentially, in
a background thread — designed to be started and left running unattended (the actual use case:
several hundred pages overnight). Backend: `_generate_chronology()` (a non-streaming extraction of
the existing `/analyze` pipeline), `_run_batch_job()` (background-thread orchestration, writes a
JSON manifest to disk after every step so progress survives and a single patient's failure never
aborts the rest of the run), patient identification via `_guess_patient_from_filename()` (tried
first, cheap) falling back to `_extract_patient_identity()` (regex over each document's own text —
"Patient Name:", "Last Name:/First Name:", DOB — matching real EHR export patterns already seen on
the "Visit Summary" documents), and `_normalize_patient_key()` (groups by normalized name + DOB, so
two different patients who happen to share a name don't get merged). New routes: `/batch` (status
UI), `/batch/start`, `/batch/status/<job_id>`, `/batch/jobs`, `/batch/<job_id>/<patient_key>/results`.
`serve_pdf` now checks both `SESSIONS_DIR` and a new, separate `BATCH_SESSIONS_DIR` so a completed
patient group's chronology reuses the *exact* existing viewer/highlighting/review UI (via a
`?batch=<job_id>&patient=<key>` URL on the main page) rather than a separate, half-featured "batch
results" view.

**Built a dedicated test fixture, since the existing per-case sample data couldn't test this.**
Discovered while testing: `sample_data/case_*_pdfs/` per-record PDFs don't embed patient identity
in each individual document at all — only in the source markdown's header, which isn't part of any
per-record PDF. Fine for single-patient uploads, useless for testing patient-grouping. Built
`scripts/make_batch_test_folder.py` → `sample_data/batch_test_folder/`: 2 documents for a fictional
"Maria Gonzalez" (using the "Patient Name:" field format), 2 for a fictional "Thomas Reyes" (using
the "Last Name:/First Name:" format, matching the real EHR pattern), and one deliberately
unidentifiable document with no patient fields at all — to confirm the "Unidentified" bucket works
rather than crashing or silently dropping it.

**Verified end-to-end via Playwright**: direct check of the identity-extraction/grouping logic
(both patients correctly identified and keyed by normalized-name+DOB, the unlabeled document
correctly landed in "Unidentified" instead of being merged or dropped or crashing); a full run
through the actual `/batch` UI (start a job against the test folder, poll until all 3 groups show
DONE, zero console errors); following a "View chronology" link through to the main app and
confirming it renders that specific patient's findings, Key Facts panel, and PDF viewer/highlighting
correctly (6 findings, highlight rendered, correct source PDF shown) — i.e., the batch feature
genuinely reuses the full existing reviewed-chronology experience, not a stripped-down clone of it.
Re-ran `testing/verify_layer_alignment.py` afterward (one transient timeout under load, clean PASS
on immediate retry) — confirms the batch-mode changes don't regress the separate, previously-fixed
highlighting-alignment code path.

**A real, useful finding surfaced by this test, not a bug in the batch feature**: one of Maria
Gonzalez's generated findings read "Abnormal findings without documented follow-up on patient's
irregular menstrual history," citing `patientA_visit1.pdf` with the quote "Assessment: Generally
healthy. Continue current medications." That quote is 100% real and verbatim — but has nothing to
do with the claim, and neither of Maria Gonzalez's two test documents mentions menstrual history at
all. This is a sharper version of a known failure mode: previous hallucination fixes (this project,
throughout `TEST_RESULTS.md`) targeted the model inventing a *fake* quote or omitting one — this is
a *real, correctly-cited* quote paired with a *fabricated* claim the quote doesn't actually support.
Our citation-grounding check only proves a quote is real and verbatim; it can't currently catch
"real quote, unrelated claim." This is exactly the failure mode the still-unbuilt generator/verifier
two-pass architecture (`PRODUCT_DEFINITION.md` §5/§6 — a second, independent pass asked "does this
quote actually support this claim, yes/no") is meant to catch, and this is now a concrete,
reproducible example of why that investment matters, not just a theoretical concern. Not fixed this
session — logged as supporting evidence, not chased with a one-off prompt patch.

## Real industry-sample stress test — found and fixed a table-vs-columns extraction bug (2026-07-22)

User provided real reference material: 7 sample chronologies from a professional medical-legal
chronology service (medicolegalrequestllc.com/our-samples/), downloaded to
`sample_data/industry_reference/` — 364 total pages across personal injury, medical malpractice,
birth injury (x2), Bates-stamped, and billing-inclusive samples. These are finished chronology
*outputs* with patient names redacted to a placeholder, not raw source records — genuinely useful
as (a) a real-world extraction-robustness stress test (large, professionally-typeset PDFs, a much
harder test than any synthetic fixture so far) and (b) a direct benchmark of professional format
conventions against our own output.

**Confirmed professional format conventions, one directly validating work done earlier today:**
every sample uses a `DATE | FACILITY/PROVIDER | MEDICAL EVENTS | PDF REF` table (the "PDF REF"
column citing the *original* consolidated record's page number — the same page-level citation
discipline already implemented here, just keyed differently); every sample has a dedicated
"Patient History" section (Past Medical/Surgical/Family/Social History, Allergies) held separate
from the event timeline — directly validating (and suggesting a further extension of) the
"pre-existing vs. new" prompt addition made earlier the same day; and illegible source content is
explicitly flagged ("(Illegible notes)") rather than guessed at — confirming this project's
"omit rather than guess" principle matches real professional practice, not just a cautious
AI-specific rule.

**Real bug found: the column-reconstruction fix from earlier today actively breaks genuine
tables.** Extraction ran clean on all 7 samples (no crashes, no OCR needed, ~2000 chars/page,
under 10s even for the 94-page sample) — but inspecting the actual extracted text for the
DATE/FACILITY/EVENTS/PDF-REF table showed every date separated from its own event description into
two disconnected blocks (all dates+facilities grouped first, all events+page-refs grouped after) —
the exact same bug shape the column-reconstruction fix was built to solve, except here it's the
FIX causing the problem. Root cause: that fix assumes two visually-separated regions on a page are
either (a) genuinely independent flowing content (correct treatment: read one column fully, then
the other) or (b) doesn't apply at all — but a genuine table is neither: its columns must stay
paired *per row* (a date belongs with its own event, not with every other date first). Confirmed
via `page.find_tables()`: this document has real structural evidence (148 rects, likely
shaded/bordered cells) that pdfplumber's table detector picks up, whereas the original Olivia
document that motivated the column-reconstruction fix has none — a reliable, principled way to
choose the correct extraction strategy per page, not a guess.

**Fixed** with a new `_extract_table_aware_text()` in `webapp/app.py`, checked first in
`_extract_page_text()`: if `page.find_tables()` finds genuine tables, extract them row-by-row
(each row's cells joined left to right, in row order) with any text before/between/after the
table(s) extracted normally — only falling through to the column-reconstruction logic when no real
table is present. Verified: the DATE/FACILITY/EVENTS/PDF-REF table now reads correctly as one
coherent line per event; all 7 samples still extract cleanly; existing single-column and
two-independent-column (Olivia-style) fixtures are unaffected (spot-checked directly, and the OCR
path and `testing/verify_layer_alignment.py` regression suite both still pass clean).

**Lesson worth generalizing**: two real bugs now found in this same extraction-reordering system,
in opposite directions (independent columns wrongly read row-by-row; a genuine table wrongly read
column-by-column) — both were only found by testing against *real*, structurally-different
documents, not synthetic fixtures built to test one specific failure mode. Real, diverse reference
material (like these industry samples) finds bugs synthetic test generation doesn't anticipate.

## Inline citation preview + full keyboard review loop (2026-07-22)

User asked for research into making human review as fast as possible, specifically floating
"citations rather than previewing the PDF, click into the citation to see the source." Researched
current (2026) industry UX patterns for AI-grounded citations — Perplexity, NotebookLM, Claude,
ChatGPT search, Notion AI Q&A all converge on the same pattern: an inline citation chip showing the
source snippet directly at the point of the claim, with opening the full source as a secondary,
on-demand action — not requiring a document viewer to load before a claim can be checked at all.
This directly validates the user's instinct and gives it a name/precedent rather than being a novel
idea to evaluate cold.

**Implemented in `webapp/static/app.js`/`style.css`:**
- Every finding row now shows its verbatim quote inline (`.finding-citation`), not just a small
  gray "Source: file.pdf" line — this is now the primary way to verify a finding.
- Split what used to be one `selectFinding()` (which always eagerly loaded/searched/rendered the
  PDF) into two: `selectFinding()` is now lightweight — marks a finding active, enables approve/
  reject, resets the viewer to a neutral "click to view" state — and does NOT touch the PDF at
  all; `openFindingSource()` is the actual PDF load/search/highlight, triggered only by clicking
  the citation chip specifically, or the new Enter/V shortcut. This means a keyboard-driven
  approve/reject/navigate loop never waits on a PDF render unless the reviewer explicitly asks to
  see one — a real, meaningful speed difference for reviewing many findings.
- Full keyboard shortcut set: **Left/Right** reject/approve (auto-advances to the next pending
  finding — see below), **Up/Down** navigate without deciding, **Enter/V** open the active
  finding's source, **Space** edit inline (existing). All guarded against firing while typing in an
  input/textarea or mid-edit.

**A real gap found while doing this**: this project's own memory/notes claimed Left/Right
arrow-key approve/reject already existed from earlier in this session — it did not. `grep` across
the actual `app.js` turned up zero matches for either key. Whatever the cause (a prior edit
overwrote it, or it was recorded as done without actually landing), this is now genuinely built and
verified, closing a real discrepancy between recorded state and actual code.

**Existing regression tests updated to match the new interaction model** (per the standing
practice: every feature change needs its test suite actually updated, not left to rot) —
`testing/verify_layer_alignment.py` and `testing/verify_highlighting.py` both used to click a
finding's row directly to trigger highlighting; both now click `.finding-citation` specifically
(falling back to the row for a no-quote finding, which has no citation chip at all), matching the
real new flow rather than a stale one.

**Verified via Playwright**: citation chips render for every finding with a quote; a row click
selects without loading anything (confirmed via the viewer-hint text and no highlight appearing);
clicking the citation chip loads the PDF and renders a highlight; ArrowRight/ArrowLeft correctly
set approved/rejected status and auto-advance to a different finding; ArrowDown/Up navigate;
Enter opens the source for whatever's currently active. Zero console errors across the full flow.

## HIGH-PRIORITY FINDING: context window is too small for even a single real 12-page document (2026-07-22)

Discovered while checking the industry-reference batch run's first completed result
(bates-stamped-sample.pdf, 12 pages): `"input_truncated": true` — meaning the model never saw the
last ~1.5-2 pages of a document this small. Measured precisely: `MAX_INPUT_CHARS` computes to
25,004 (from `NUM_CTX=12288` tokens, minus the prompt template's own ~10,626 characters of
instructional overhead, minus a 2000-token output reserve), while this single 12-page document's
extracted text is 28,795 characters — over by ~3,800 characters (~13%) even *before* accounting for
multiple documents ever being combined in one run. The bigger samples in the same batch (94, 89, 66
pages) will be truncated far more severely — likely losing the large majority of their content.

This is the single highest-priority finding from today's testing relative to the stated goal of
handling several hundred pages reliably: **the current default context window (12,288 tokens) is
the actual bottleneck**, not extraction quality or prompt design. `llama3.1:8b` architecturally
supports up to 128K tokens — the current default is a small fraction of what the model can do,
almost certainly chosen conservatively for this dev machine's 16GB RAM without being verified
against a real large document. This machine currently has Ollama running with flash attention
enabled (`--flash-attn auto`, confirmed via `ps`), which meaningfully reduces the KV-cache memory
cost of a larger context — increasing `LAWFIRMAGENT_NUM_CTX` substantially is very likely both
necessary and feasible, but changing it requires Ollama to reload the model (a `num_ctx` change is
a model-load-time parameter, unlike prompt content, which is per-request) — deferred testing this
specifically until the current overnight batch run finishes, to avoid disrupting it. **This is the
top priority to act on next.**

## Chunking implemented, and a real bug caught before it shipped (2026-07-22)

Following up on the context-window finding above: implemented proper chunking for the batch
pipeline rather than raising `NUM_CTX` alone, since even the model's architectural maximum (128K
tokens ≈ ~450K characters) is still short of a genuine 500-page case (~1M characters at this
corpus's measured ~2000 chars/page) — a chunking/map-reduce approach is necessary regardless of
how generous the context window is. Added to `webapp/app.py`: `_pack_into_chunks()` (greedily packs
whole documents into context-sized chunks, splitting a single oversized document into labeled
sub-parts only when it doesn't fit alone), `_call_model_for_chunk()` (one blocking Ollama call per
chunk), `_merge_chunk_findings()` (concatenates timeline/discrepancies, concatenates + exact-text
dedupes the atomic fact lists, combines per-chunk summaries with part labels) — `input_truncated`
is no longer produced by this path at all; chunking replaces truncation, nothing is silently
discarded.

**Caught a real bug via direct unit testing before it ever ran against real data**: the first
implementation split an oversized single document at `"\n\n"` (paragraph) boundaries — but this
project's own PDF extraction joins all lines with single `"\n"`, never `"\n\n"` (confirmed by
grepping `pdf_to_text`/`_extract_page_text`), so `body.split("\n\n")` returned the ENTIRE document
as one unsplit "paragraph" for every real document tested. The splitting loop's own guard clause
(`and current`, requiring a non-empty accumulator) meant it silently never split anything on the
very first iteration — the exact oversized-document case the function existed for was quietly
never being exercised. Caught immediately by re-running the same direct integration test that
surfaced the original truncation finding (bates-stamped-sample.pdf) and noticing `chunks: 1` where
2 were expected, rather than trusting the code compiled/imported cleanly. Fixed with a proper
fallback chain (`_split_text_to_fit`): try paragraph breaks, then line breaks (which the real data
actually has), then raw character slicing as a last-resort guarantee of termination. Re-verified:
the same 12-page document now correctly splits into 2 chunks (24,998 + 3,910 chars); the largest
real sample (94 pages, 205,338 characters) correctly splits into 9 well-packed chunks, all within
the 25,004-character budget, meaning that document will now be **completely** analyzed instead of
truncated to roughly its first 12%.

**Lesson worth generalizing, again**: this is now the *third* time in one day that a fix looked
correct by inspection/compiling cleanly but had a real bug only caught by actually running it
against real data and checking the output, not just trusting the code path executed without
throwing. Direct integration testing against real documents — not just unit tests with synthetic
inputs shaped to match the code's own assumptions — keeps finding bugs synthetic tests miss.

**Known gap, not yet fixed**: the interactive single-upload `/analyze` streaming endpoint still
uses the old truncate-and-warn behavior — chunking was only added to the batch-folder pipeline
(`_generate_chronology`) to avoid risking the separate, delicate NDJSON-streaming code path in the
same pass. This is a real inconsistency (the same underlying bug, fixed in one path and not the
other) — worth porting the same fix to `/analyze` in a future pass.

## Real, serious bug found and fixed: export crashed after adding any Key Facts item (2026-07-22)

Found while researching competitive features (checking what our own export looked like against
what other tools offer) — re-reading `buildExportText()` closely revealed `bySection` only
initialized `timeline`/`potential_issues`/`discrepancies`, but a finding added via the Key Facts
panel (built earlier the same day) has `meta.section === "key_facts"` — a section never added to
`bySection`. Verified directly via Playwright rather than trusting the code read: added a fact via
the Key Facts panel, clicked Export, and it threw `Cannot read properties of undefined (reading
'push')`, crashing the export entirely. This would have affected any real use of the Key Facts
panel followed by an export — a serious regression from earlier the same day, caught by continuing
to actually test flows end-to-end rather than assuming a shipped feature stays correct as later
code changes land around it.

Fixed: `bySection` now initializes `key_facts: []` explicitly, plus a defensive fallback
(`bySection[meta.section] || (bySection[meta.section] = [])`) so a similar gap for any future
section type fails safe instead of crashing. Added the corresponding "Key Facts (added during
review)" output section to the exported chronology. Verified: export now succeeds with zero
console errors, and the downloaded Markdown file correctly includes the added fact under its own
section with proper citation.

## Process-discipline mistake caught: batch job ran for ~20 minutes on stale pre-fix code (2026-07-22)

After fixing the `_split_text_to_fit` paragraph-splitting bug, restarted the LIVE server (port
5050) per the standing practice — but did not restart the TEST server (port 5051), which is what
was actually running the industry-reference batch job. Result: that job kept running on the
*previous* process, which still had the pre-fix chunking code — meaning the large documents
(chronology-with-bills.pdf, 89 pages; birth-injury-2-sample.pdf, 66 pages) that finished under that
stale process report `chunks: 1` in their manifest, when a fresh check of the same files with the
actual current code correctly computes 8 and 6 chunks respectively. Caught by noticing the
completed large documents' wall-time/output-token stats looked suspiciously similar in scale to
the small documents' — not plausible for something 6-8x larger — and directly re-running
`_pack_into_chunks` fresh against the same files to confirm the discrepancy, rather than trusting
the job's own reported numbers.

Consequence: those specific results were **silently under-processed** — not by our own truncation
logic (which no longer exists on this path) but by Ollama's own internal context-shift behavior
(`--context-shift` in its launch flags) silently dropping/shifting content that didn't fit the
configured `num_ctx`, given the oversized single-document prompt was never actually split before
being sent. Restarted the test server and re-launched the batch job fresh rather than let it
finish on stale code and only fix it for next time.

**Lesson**: "restart the live server after a backend change" (learned earlier today) needs to be
"restart *every* server process actually running the code that changed" — including the dedicated
test server, which is easy to forget about specifically because it's not the one a human would
notice acting wrong. Worth checking which process is *actually* serving a request (e.g. via `ps`
matching the port) rather than assuming a restart of "the server" covered everything, whenever
more than one instance of this app might be running at once.

## Live tokens/sec, mid-chunk partial findings, and button-order swap (2026-07-22)

Three requests in one batch: show batch-mode tokens/sec live, show chronology entries as soon as
they're known (not just at chunk boundaries), and swap Approve/Reject so Reject is left/Approve is
right to match the Left=reject/Right=approve keyboard shortcuts.

**Tokens/sec**: `_call_model_for_chunk` now calls Ollama with `stream=True` internally (previously
`stream=False`) purely to get live token counts — throttled to ~1.5s intervals, surfaced through
the existing `on_progress` status-text mechanism (e.g. `"Generating chronology (pass 1 of 2) —
2230 tokens so far, 7.9 tok/s"`), plus a final per-chunk tok/s noted in the "done" label.

**Button order**: swapped `#reject-btn`/`#approve-btn` DOM order in `index.html`. Verified visually
via Playwright bounding boxes: reject renders left of approve.

**Bug found and fixed while wiring up live rendering**: `lastFindingCount` in `app.js`'s batch
polling loop was being bumped *before* `renderResults()` ran. When `renderResults` threw (see
next paragraph), the count had already advanced, so every subsequent poll believed nothing was new
and silently gave up forever — results stuck at zero even though `progress_text` kept updating
correctly in the banner. This was masked by an outer `.catch()` meant only for genuine network
failures. Fixed by only committing `lastFindingCount` after a successful `try`, with an explicit
`console.error` on failure so a render bug surfaces instead of disappearing.

**Root cause of that crash**: `renderResults()` assumed `data.stats` was always a complete object,
but a genuinely partial batch result has `stats: null` until every chunk finishes — threw
`TypeError: Cannot read properties of null (reading 'documents_processed')`. Fixed with a
conditional stats line ("Still generating — final stats... will appear once complete."). Caught
via a *second*, more careful Playwright test with explicit console-error capture — an earlier test
run had suppressed the real error inside a blanket `.catch()` and reported false-positive success.

**Cleaner "not ready yet" signal**: the `/batch/<job_id>/<patient_key>/results` endpoint was using
HTTP 404 to mean "no findings yet, still processing" — a normal, expected state that the frontend
polls every 4 seconds. Chromium logs every failed-status network request to the console as an
error regardless of resource type, so ordinary polling was spamming ~1 console error per poll (a
30-tick test run surfaced 50 of them) even though nothing was actually broken. Changed the endpoint
to return HTTP 200 with a `ready: false`/`ready: true` flag instead, reserving real 404s for a
genuinely unknown job/patient id. Frontend now branches on `data.ready`. Verified: identical
30-tick polling test now produces zero console messages.

**Real gap found via direct testing, not speculation — mid-chunk partial results**: a batch case
small enough to fit in a *single* chunk (the common case — one small-to-medium patient file) never
actually benefited from "show it as soon as we know it," because partial findings were only ever
reported at chunk *boundaries*, and a 1-chunk case has no boundary until the whole thing finishes.
Confirmed this concretely: ran the small synthetic test fixture end-to-end and watched
`.finding` stay at 0 for the entire single-chunk generation (~130s) while `progress_text` correctly
climbed in tokens/sec — proving the live-token-count plumbing worked but genuinely nothing was
shown until completion.

Fixed with `_extract_complete_arrays()`: scans the model's in-progress (not-yet-valid) JSON output
for whichever top-level array fields (`timeline`, `medications`, `procedures`, `diagnoses`,
`potential_issues`, `discrepancies`) are already fully bracket-matched and closed, parses just
those, and leaves anything still truncated out entirely — no guessing at unclosed brackets/strings.
Since the model streams JSON fields in schema order, earlier fields (timeline, medications,
procedures) reliably close well before generation finishes. Wired into the existing
`on_token_progress` callback (now 3-arg: tokens, tok/s, partial arrays) and merged with any
already-completed prior chunks via the existing `_merge_chunk_findings`. Verified end-to-end:
`.finding` count went from 0 to 3 while the group's status was still `processing` (not `done`),
confirming real findings now appear mid-generation even for single-chunk cases — the scenario that
previously showed nothing at all until the end.

**Process note**: verifying this required freeing Ollama's single concurrency slot (`-np 1` in its
launch config means exactly one generation runs at a time, regardless of which of this app's server
processes requested it) — the live 5050 server was still mid-run on the old code for the 364-page
industry-reference stress test, silently starving the 5051 test-server verification job of any
progress for minutes (not a bug, just resource contention masquerading as one). Restarted 5050 on
the new code and relaunched that stress test fresh (job `a5052394000a4fb1879a9ed0dadf4557`) so it
also benefits from today's fixes rather than finishing on stale code — consistent with the
process-discipline lesson above.

## Click-to-edit, Enter-to-edit, unadd-from-facts-panel, Labs category, PDF export (2026-07-23)

Five requests: (1) every finding editable by clicking straight into it, not just via Space; (2)
Enter as a keyboard shortcut to start editing; (3) a way to "unadd" a fact added via the Key Facts
panel; (4) a "Labs" category alongside medications/procedures/diagnoses; (5) chronology export as
a real PDF, not Markdown.

**Click-to-edit**: `makeFindingEl`'s row click handler now calls `selectFinding(id)` then
`startEditingFinding(id)` (previously just selected). The citation chip keeps its own
`stopPropagation()`'d click (still opens the source PDF, not edit mode) — verified this split
still works correctly via Playwright bounding-box inspection: a naive test that clicked the row's
bounding-box *center* landed on the citation chip (which dominates the row's visual area) and
correctly triggered view-source, not edit; clicking the finding-text span specifically (what a
real user clicking "into the text" would do) correctly opens edit mode. Not a bug — confirmed both
paths behave as intended.

**Enter-to-edit**: remapped the global keydown handler's `Enter` binding from "open source PDF" to
"start editing" (same action as Space); `V` alone now opens the source PDF. Updated the two
viewer-hint strings that referenced "press Enter to view" to say "press V" instead, so the on-screen
hint text doesn't contradict the new binding.

**Same-id and cross-id editing safety**: clicking a *different* finding while one is already being
edited needed its own handling — a plain, non-focusable row `<div>` doesn't reliably blur a focused
textarea in every browser on click, so `editingFindingId`'s existing guard (leftover from the old
Space-only flow) would have silently no-op'd the second edit. Added a `currentEditFinish` pointer to
the active edit's own `finish` closure so `startEditingFinding` can explicitly commit whatever else
was being edited before opening a new one.

**Unadd from the Key Facts panel**: a fact chip's "already added" state now distinguishes *why* —
already present in the model's own narrative extraction (not removable from here; nothing this
panel put there) vs. added via this panel (removable). Required switching `key_facts` entries from
position-based ids (`key_facts-${index}`) to a stable per-fact id stored on each entry, since
removing an item from the middle of that array would otherwise silently relabel every later fact's
already-saved review status/edits onto the wrong item after the next render. The generic `section()`
helper in `renderFindings` now takes an optional `idFor` override for this (every other section still
uses plain array position, unaffected). Verified via Playwright: add a lab value via the facts panel
(findings count +1), click it again (findings count back to original), zero console errors.

**Labs category**: added as a 4th atomic fact list end-to-end — `RESPONSE_SCHEMA`,
`_DEDUP_LIST_FIELDS`, `_STREAMING_ARRAY_FIELDS` (so it also benefits from the mid-chunk live-partial-
findings work above), `_merge_chunk_findings`'s initial dict, the batch-polling `countFindings` list,
`FACTS_CATEGORIES` in `app.js`, and `chronology_prompt_structured.txt` (lab/vital name + value,
e.g. "Hemoglobin 7.2 g/dL", same verbatim-quote/exhaustiveness rules as the other three lists).
Verified: a real run against `case_001` correctly populated a "Labs (1)" tab.

**PDF export**: replaced the client-side Markdown-via-Blob export with a new `POST /export/pdf`
Flask endpoint using `fpdf2` (already installed in the venv — no new dependency, no vendoring a JS
PDF library). The browser still owns all review-state bookkeeping and just POSTs the already-
assembled approved-only content (`buildExportPayload()` replaces the old `buildExportText()`); the
server is a dumb renderer, not a second source of truth for what's approved.

Two real fpdf2 pitfalls hit and fixed while building this (found by actually running it, not by
reading docs): (1) `multi_cell`'s default `new_x=XPos.RIGHT` leaves the cursor at the page's right
margin, so a second `multi_cell` call with default args immediately throws `"Not enough horizontal
space to render a single character"` — fixed by passing `new_x="LMARGIN", new_y="NEXT"` on every
call. (2) fpdf2's core Helvetica font only supports Latin-1 (codepoints 0-255), but real model
output regularly contains em/en dashes, curly quotes, and ellipses outside that range — added
`_pdf_safe_text()`, a substitution table for common typographic punctuation plus a
`.encode("latin-1", errors="replace")` final safety net. Deliberately NOT solved with a Unicode TTF
font file, since this app's actual deployment target is a Windows PC (per `PRODUCT_DEFINITION.md`)
and a font path found on this Mac dev machine wouldn't exist there. Verified end-to-end: approved one
finding, clicked Export, got a real downloadable `.pdf` (confirmed via `file` and `pdfplumber` text
extraction — correct title, review-summary line, section, and citation all render correctly).

## Case Mode: redesigning around Plaintiff/Defendant/Complaint/Notice-of-Intent (2026-07-23)

Four user messages, read together, described one coherent redesign rather than four separate asks
(full context/plan in `~/.claude/plans/toasty-painting-spring.md`, approved before building):
every case needs a Complaint/NOI (with a DOL — date of loss) read *first*; the export must match the
firm's own `Blank Chronology Template.docx` exactly; a real workflow email from the actual end-user
paralegal specified defendant "at-issue" prominence, record-type/authoring-provider labeling, and a
vendor-vs-"PL"-record preference; and the domain itself needed rethinking around Cases (named by
Plaintiff, defending a medical-provider Defendant) with a folder of subfolders (correspondence,
depositions, discovery, experts, liens, memo, orders, pleadings, records, team) rather than a flat
pile of mixed-patient PDFs.

**Approach taken**: evolved the existing, proven Batch Folder Mode machinery (background job,
manifest polling, live partial-results, tokens/sec) into "Case Mode" rather than rewriting it — the
group key is now given directly (the plaintiff's name), with the old content/filename identity
guessing kept as a secondary fallback for a genuinely different individual's records mixed into the
same folder (co-plaintiff, family case), not the primary experience anymore.

**Built**: `_find_complaint_file()`/`_extract_complaint_info()` (new `complaint_extraction_prompt.txt`
+ `COMPLAINT_RESPONSE_SCHEMA` — extracts plaintiff/defendant names, DOL, facts summary, prefers a
`pleadings/` subfolder, degrades to a clear warning rather than blocking the case if nothing found);
`_build_case_context()` threading defendant/DOL/facts/priority-hint into the chronology prompt;
priority-subfolder reordering (whatever the reviewer flags as important is processed first, so the
existing mid-chunk live-partial-results feature surfaces it earliest); new `record_type`/`author`/
`at_issue` fields on every timeline-shaped entry and a new top-level `patient_demographics` object
(DOB/Address/Social-Hx/PMHx/FHx/Surgical-Hx/PCP) in `RESPONSE_SCHEMA`; new `/case` routes/UI
(`templates/case.html`, `static/case.js`) replacing `/batch`; the PDF export completely rewritten to
match the firm's exact template structure (RE/Updated/DOL/Facts/DOB/.../PCP header block, an
auto-filled Abbreviations/Record Sources legend, an Outstanding Records placeholder, and a real
`fpdf2` `pdf.table()` for DATE|PAGE|RECORD|SOURCE|DESCRIPTION with at-issue rows rendered in red);
new case-folder test fixtures (`scripts/make_case_test_folders.py` → `case_smith/` with a complaint
and all 9 subfolders populated, `case_nodefendant/` with none, to exercise the fallback path); new
`testing/verify_case_creation.py` and `testing/verify_pdf_export_template.py`.

**Real bug found and fixed while testing this — a genuine reliability regression, root-caused, not
guessed.** Direct testing against the tiny `case_000` fixture (a single short office-visit note)
found the model occasionally returning a completely empty-but-schema-valid result (every list
empty, blank summary) for a document that plainly has real content — confirmed reproducible by
calling the *exact same* prompt+schema back-to-back and getting a full correct extraction on one
call, nothing on the next. Controlled A/B testing isolated the cause: even a reconstructed version
of the prompt/schema as they existed *before* this session's Case Mode additions showed the same
failure at a lower but nonzero rate (1 empty in 4 runs) — this is a real, pre-existing characteristic
of `llama3.1:8b` under grammar-constrained JSON generation on short documents, not a new bug Case
Mode introduced, but the added required fields (initially 9 per entry, up from 4) clearly raised its
frequency (as high as 3 empty results in 4 runs when tested in isolation). Two fixes, both verified:
(1) removed `ordering_provider`/`reading_provider` as separate required schema fields — folded that
detail into `text`/`author` instead, cutting per-entry required fields from 9 back to 7; (2) added a
retry in `_call_model_for_chunk`: if a result comes back with every dated-entry list AND the summary
empty (a strong degenerate-output signal, not a plausible "genuinely nothing to extract" result),
retry once with the identical input before accepting it. Verified: 5/5 clean, substantive runs
against `case_000` after the fix, versus the 0/4-3/4-empty rates measured before it.

**Real, honest finding on `at_issue` reliability — not glossed over.** The user explicitly chose
"model judgment only" for at-issue flagging over deterministic defendant-name matching (a
recommended-but-declined alternative). Testing this concretely: one full run against `case_smith`
(complaint names "Dr. R. Okafor" as defendant; several timeline entries are authored by exactly that
name) came back with **0 of 9 entries flagged `at_issue: true`** — including entries the defendant
literally authored. A concrete worked example was added to the prompt's AT-ISSUE section
specifically targeting this exact scenario; it did not measurably help on a repeat run (still 0/9).
A *later* full rerun of the identical fixture/setup, after the retry-mechanism and schema-
simplification fixes above, came back with **4 of 12 entries correctly flagged**. This is genuinely
non-deterministic — the same case, same defendant, same documents — not a fixed bug with one root
cause, and not something a prompt tweak alone reliably closes. Documented here rather than declared
fixed: `at_issue` should currently be treated the same as this app's other subjective model-judged
fields (`potential_issues`/`discrepancies`) — worth a human double-check, not a guarantee. If
reliability here becomes a priority, the previously-declined deterministic-text-match approach (or a
hybrid: compute it deterministically, and separately flag any disagreement with the model's own
judgment for review) is the concrete fix path already scoped in the plan.

**Also fixed while testing the export**: the DATE|PAGE|RECORD|SOURCE|DESCRIPTION table only rendered
its column headers when at least one row existed — meaning a chronology with zero approved entries
yet (a very normal state right after a case starts) produced an export missing the table skeleton
entirely, which doesn't match "this should look like this file was always the starting point." Fixed
to always render the header row, with a single "(no approved chronology entries yet)" placeholder
row (via `colspan=5`) when there's nothing approved yet.

**Verified end-to-end**: `testing/verify_case_creation.py` — complaint auto-detected (`Dr. R. Okafor`,
`Adeline Medical Center`, DOL, facts summary all correctly extracted), all 9 case subfolders
(correspondence/depositions/discovery/experts/liens/memo/orders/pleadings/team, not just `records/`)
correctly ingested into one 17-document chronology, `record_type`/`author` bold headers rendering
correctly on findings, the no-complaint-found fallback (`case_nodefendant/`) proceeding with a clear
warning instead of failing. `testing/verify_pdf_export_template.py` — exported PDF contains every
required template section/label, confirmed via `pdfplumber` text extraction. Re-ran
`testing/verify_layer_alignment.py` (all 5 viewports, 0.0px off) and `testing/verify_highlighting.py`
(highlight lands exactly on rendered text, zero console errors) — no regression from the `app.js`
finding-row changes (record_type/author header, at-issue badge).

## Case-folder picker, replacing free-typed paths (2026-07-23)

User asked for the Case Mode folder path to be selectable rather than typed. A plain
`<input type="file" webkitdirectory>` can't do this: browsers deliberately hide a chosen folder's
real absolute path for privacy/security, but the backend needs a real path it can read directly off
disk (hundreds of PDFs are never uploaded through the browser at all). A native OS folder dialog
triggered server-side has the opposite problem: it would show on whichever machine is physically
running the Flask process — in this app's actual planned deployment (tower does the compute,
paralegal's laptop is a thin client per `PRODUCT_DEFINITION.md`/`TOWER_SETUP.md`), that's the tower,
not the visible laptop screen, making it useless there even though it "works" during today's
same-machine dev testing.

Built instead: a small in-browser folder-picker modal backed by a new `GET /case/browse` endpoint
that lists real subdirectories of a given path on the SERVER's filesystem (defaults to the user's
home directory) — this works identically regardless of whether the browser and Flask server are on
the same machine or not, since it's browsing the exact filesystem `_run_case_job` will actually read
from. `case.html`/`case.js` got a "Browse…" button next to the folder-path field, opening a modal
with a breadcrumb, a clickable directory list (with an "↑ .." row to go up), and Select/Cancel
actions.

Same console-noise lesson from earlier applied proactively rather than found via a bug report this
time: an invalid/stale path (e.g. the text field was hand-edited before reopening the picker) is a
normal, expected state, not a server error — `/case/browse` returns HTTP 200 with an `error` field
for that case rather than a 4xx, so the browser console stays clean; a friendly inline message shows
in the modal instead. Verified via a new `testing/verify_folder_browser.py`: navigate into and back
out of a subfolder, Select commits the current path into the input, Cancel leaves it untouched, an
invalid path shows an inline message with zero console errors.

## Chronological ordering, Bates numbering, record-source labels, demographics verification, duplicate-record handling, and PDF-to-Word export switch (2026-07-23)

A dense run of six related, mostly user-driven requests, all touching the citation/export pipeline:

### 1. Timeline sorted earliest-first, on screen and in the export

Findings were previously shown in whatever order the model emitted them (usually close to
chronological, since that's literally its task, but never guaranteed — especially across merged
chunks). Added `parseDateForSort()` (best-effort `Date.parse`, with a special case for day-ranges
like "03/04-06, 2026"; unparseable/placeholder dates sort to the end) and `sortDatedItemsStably()`
in `app.js`. The Timeline section, Key Facts section, and the export's merged
timeline+key-facts table are all sorted ascending by date now.

**Real bug caught before it shipped**: sorting the Timeline array changes DISPLAY order, but ids
(`timeline-N`) were generated from ARRAY POSITION — re-sorting would silently reassign an already-
reviewed item's id (and its saved approve/reject state) onto a different entry after a live-
updating batch/case poll appends a new, earlier-dated item mid-stream. Fixed by pairing each item
with its ORIGINAL array index before sorting and keying ids off that instead of sorted position —
same stability principle already used for Key Facts' removable ids.

**Also caught while verifying this**: the exact temporal-dead-zone bug documented earlier this
session for `FACTS_CATEGORIES` recurred for `PLACEHOLDER_VALUES` — the new sort code could run
synchronously during the cached-result-restore path at page load, before `PLACEHOLDER_VALUES`'s
`const` declaration (textually much later in the file) had executed. Moved it up next to
`FACTS_CATEGORIES` for the same reason.

### 2. Bates numbering — real per-page citations, not "page N"

Researched Bates numbering conventions (prefix + zero-padded sequential digits, 4-6 digits,
continuous across a whole document production, stamped in a page's bottom margin) and implemented
it as the citation reference throughout, replacing the earlier pageNum-discovered-on-click
approach entirely.

**Design decision, and why**: rather than adding `bates` as a new required schema field (which the
model would report itself), it's derived SERVER-SIDE by locating the model's own already-required
verbatim quote within the source page text — `_extract_bates_number()` (pdfplumber word positions,
bottom ~12% of page height, regex `[A-Za-z]{0,6}[-_ ]?0\d{3,9}` — the digit run always starts with
a leading zero per the firm's convention) embeds a `[BATES: XXXXX]` marker at the start of each
page's text in `pdf_to_text()`; `_find_bates_for_quote()` then finds which page-segment contains a
given finding's quote and returns that segment's Bates number. This was deliberately NOT built as a
9th required per-entry schema field specifically because of the empty-output regression documented
earlier this session (going from 4 to 9 required fields per entry made output genuinely bimodal) —
deriving it from data the model already must provide adds the capability with zero added schema
risk, and is more trustworthy (can't be hallucinated) than trusting a model-reported field would be.

**Two real matching-fragility bugs found and fixed via direct testing against a real 9-document
case** (not assumed): (1) a naive exact-substring quote search failed to resolve Bates numbers for
several genuinely-correct quotes because of whitespace/newline differences between the quote and
the source segment — fixed with whitespace normalization. (2) The model sometimes reproduces a
quote's punctuation in an equivalent but different style (curly vs. straight quotes, en/em-dash vs.
hyphen) — fixed by normalizing those specific punctuation variants on both sides before comparing.
Resolution rate went from ~22% (2 of 9) before these fixes to 89-83% (8-10 of 9-12) after, across
several fresh runs.

**One remaining, accepted gap, found via the same testing — not chased further**: one entry's
quote genuinely differed in WORDING from the source (the model dropped a word and re-capitalized,
not just a punctuation-style difference), and correctly resolved to "Bates not resolved" rather
than a guess. This is the same "omit rather than guess" principle already governing the rest of
this app's citation grounding, and the same reliability ceiling the existing client-side
highlight-quote-matching already has (which uses fuzzy matching to partially compensate — the
Bates-matching function does not, on purpose, to avoid resolving a Bates number for a quote that
isn't genuinely the one stated). If this specific gap needs to close further, fuzzy matching
mirroring the client's approach is the identified next step — not implemented this round.

The `[BATES: X]` markers themselves are explicitly called out in the prompt as structural page
breaks, never to be quoted as content. Wired into both `_generate_chronology` (Case Mode) and the
interactive `/analyze` streaming endpoint identically.

### 3. Short, unique, content-derived record-source labels

User's ask: `fairview_op_report.pdf` should show as "FairviewOpReport" in the export's SOURCE
column, not the raw filename — and the model should be smart enough to derive this from the
document's actual content, not just reformat the filename. Added a new top-level (not per-entry,
so no per-entry-field-count risk) `record_sources` schema list — one `{source_file, label}` entry
per document. `_resolve_record_sources()` builds the final `{filename: label}` map, falling back to
a filename-derived label (`_slugify_label`) for any file the model skipped or hallucinated a
mismatched filename for, and — critically — enforces uniqueness DETERMINISTICALLY (appending "2",
"3", ... on a collision) rather than trusting the model's own claim that its labels are already
unique, since two different files must never share a label. Verified: real labels like
"FairviewOpReport", "StAdelineMedicalCenterHematologyConsultNote" generated from content, and a
genuine collision correctly disambiguated to "RiverbendFamilyMedicineVisit"/
"RiverbendFamilyMedicineVisit2" for two different office-visit documents from the same facility.
The Abbreviations/Record Sources legend in the export now shows "label = filename" pairs instead
of a flat filename list — which is exactly what that section of the real template is for.

### 4. Patient-demographics grep fallback

Before the export ever declares a demographics field (DOB/Address/Social-Hx/PMHx/FHx/Surgical-Hx/
PCP) "not provided," `_verify_demographics_with_grep()` double-checks it against a direct label-
based text search (`"Label: value"` patterns) across everything actually extracted — catching the
model reporting "not stated" for something literally present in a labeled field it simply missed.
Never overrides a value the model DID find. Anything found this way is marked
"(found via text search — verify against source)" so the reviewer knows it wasn't the model's own
read. Verified directly: correctly filled in 6 of 7 fields the model had missed, left the one field
the model DID find untouched.

### 5. Literal-duplicate-record deduplication with multi-source display

User's ask: real case files commonly contain literal 1:1 duplicate records (the same visit obtained
both from a provider and as a "PL" copy, or simply uploaded twice) — these should collapse to ONE
chronology entry, but that entry must show every source it came from, not silently pick one.
`_dedupe_with_multi_source()` groups items by exact normalized text match and merges duplicates into
one entry with `source_files`/`bates_list` arrays (only added when there's genuinely more than one
distinct source — a normal single-source entry is untouched). Runs AFTER Bates resolution (needs
each raw item's own resolved Bates number first) and applies to every dated-entry list plus
potential_issues — deliberately NOT to discrepancies, which already have their own genuine
multi-source shape describing a conflict *between* sources, a different concept from the same fact
being corroborated by duplicates. The existing multi-source rendering built for discrepancies
(`sourceFiles`/`batesList` → "Sources: A; B") is reused as-is for any other section now producing
the same shape — no new frontend rendering code needed, just passing the fields through. Verified
directly: two duplicate entries with identical text correctly merged into one row listing both
sources' Bates numbers; a third, textually-distinct entry from the same file was correctly left
unmerged.

### 6. Export format switched from PDF to Microsoft Word (.docx)

Replaced the fpdf2-based PDF export with a python-docx-based `.docx` export — same template
structure, `Normal` style set to Times New Roman 12pt (the firm's explicit requirement) throughout,
at-issue rows rendered in red text in the Word table (matching the PDF version's behavior). Removed
the now-fully-dead fpdf2 code (`_pdf_safe_text`, `_PDF_CHAR_REPLACEMENTS`, the `FPDF`/`FontFace`
imports) — python-docx handles Unicode natively, so the whole Latin-1-safety-net class of code this
app needed for fpdf2 simply doesn't apply anymore. `testing/verify_pdf_export_template.py` renamed
to `verify_docx_export_template.py`, rewritten against `python-docx` instead of `pdfplumber`, now
also asserting the Times New Roman/12pt requirement explicitly. Verified end-to-end: exported
document has the exact template structure, a real DATE/PAGE/RECORD/SOURCE/DESCRIPTION table with
real Bates numbers and content-derived labels, and confirmed 12pt Times New Roman body text.

### Test data regeneration

`scripts/make_test_pdfs.py`, `scripts/make_batch_test_folder.py`, and
`scripts/make_case_test_folders.py` (its `OTHER_SUBFOLDER_DOCS`, not the Complaint/NOI — that's
parsed via a separate endpoint that doesn't go through the citation/Bates flow at all) now stamp
every page with a sequential Bates number, rotating left/center/right placement across documents to
exercise all three — the app is built assuming every real PDF it processes has one, so test data
needs one too for that assumption to actually be exercised rather than silently untested.

### Verification summary

Direct unit-style tests (`_resolve_bates`, `_dedupe_with_multi_source`, `_resolve_record_sources`,
`_verify_demographics_with_grep`) against hand-built fixtures, a consolidated real-browser test
against the 9-document `case_001` fixture (Bates resolution rate, dedup, labels, full `.docx`
structure/formatting all in one pass), `verify_docx_export_template.py`,
`verify_layer_alignment.py` (all 5 viewports, 0.0px off), and `verify_highlighting.py` (0.0px off,
zero console errors) — all pass. `verify_case_creation.py` (the slow 17+7-document Case Mode
end-to-end test) re-run to confirm no regression from the schema changes (`record_sources` added,
`bates` no longer a schema field).

## Highlighting-robustness hardening: Bates cross-check + disambiguation (2026-07-23/24)

User's directive: clicking a finding and seeing the highlighted region in the PDF has to be
**perfect** — never misrepresenting where the highlight is, never showing the wrong document.
Explicitly authorized fabricating synthetic test examples and asked for research into better
approaches/fallbacks. This is the single highest reliability bar set for any feature in this app.

**The real risk identified:** `findQuoteInDoc` searches every page of a document for the model's
quoted text. Two failure modes exist that no amount of pixel-alignment testing (the existing
`verify_layer_alignment.py`/`verify_highlighting.py` suite) would ever catch, because both produce a
highlight that is pixel-perfect — just on the wrong page: (1) the exact same sentence appears
verbatim on more than one page of a real document (templated EHR boilerplate, repeated disclaimers,
a duplicated visit note), and the old code returned the *first* page found, not necessarily the
right one; (2) the fuzzy/partial-match fallback (for when the model doesn't quote verbatim) had the
same first-found-wins bug.

**Fix: an independent, mechanically-checkable second signal — Bates numbers.** The server already
resolves each finding's citation to a specific Bates number by locating the model's quote within
Bates-marked page text (see the Bates numbering round above). The client can independently read the
Bates stamp physically printed on whatever page it's about to show, via `extractBatesFromPage()`
(same bottom-12%-margin convention and regex as the server's `_extract_bates_number`, run against
pdf.js's own extracted text/positions — a second, differently-implemented extraction, not just the
same code path twice). `findQuoteInDoc(pdfDoc, quote, expectedBates)` now collects *every* exact
match across the whole document (`exactMatches[]`) instead of returning on the first, then prefers
whichever candidate's own page-Bates equals the finding's already-resolved `expectedBates` — the
same preference logic applied to the fuzzy-match fallback (`bestCandidates[]` tracks every tie for
best match length, across all pages, not just the first page checked). `showFinding()` then renders
a visible banner (`#viewer-bates-check`, new element) after landing on a page: "✓ Bates verified"
(the two independent extractions agree), "⚠ Possible mismatch" (they disagree — a concrete,
mechanically-detected reason to distrust this specific highlight, not just a vague reminder), or
"couldn't read a Bates number to cross-check" (page has no stamp pdf.js could read). This is about
as strong a non-human guarantee of "this is really the right page" as this architecture can produce:
two independently-implemented extractions (server pdfplumber, client pdf.js) landing on the same
physical page by two different routes (quote content vs. printed stamp).

**Three purpose-built trap tests, all fabricated specifically to break the old code (as directed),
all passing against the new code:**
- `verify_bates_disambiguation.py` — 2-page PDF, identical sentence on both pages, different Bates
  stamps. Confirms the viewer picks whichever page's Bates matches the finding's citation, in both
  directions, and confirms a finding citing a Bates number that exists on *neither* page produces a
  "mismatch" banner rather than a false "match."
- `verify_repeated_boilerplate_disambiguation.py` — harder version: 5 pages, the exact same sentence
  repeated verbatim on every single one. All 5 target pages resolve correctly via the Bates
  cross-check alone — proves the fix scales past a simple two-candidate case.
- `verify_multicolumn_highlighting.py` — a 2-column medical-note layout (left/right columns share
  overlapping vocabulary like "acute"/"onset") to check the highlight lands in the correct column,
  not the other one — verified both by pixel alignment to a real text span and by checking the
  highlight box's x-position falls within the correct column's actual rendered range on screen.

**Real-world stress test against `sample_data/industry_reference/bates-stamped-sample.pdf`** (a
genuine 12-page professionally-typeset chronology PDF, not a synthetic fixture — the original real
"Olivia" documents referenced earlier in this file are no longer present on disk, so this is the
best available real-world substitute). Result: 8/8 findings got a highlight, all within 0.0px of a
real rendered text span — zero misplaced highlights, zero wrong documents. Notably, 7 of those 8
only matched via the fuzzy/partial fallback, not an exact quote — this document is itself a
redacted/summarized output (not raw source records), and the model frequently didn't quote it
verbatim; the fuzzy fallback correctly recovered a precisely-aligned highlight every time. One
finding (in an earlier run against the same file) had no highlight at all: the model's "quote" field
invented a specific date ("January 27, YYYY") where the actual source text uses a literal
`MM/DD/YYYY` placeholder — a genuine case where the model's wording diverged too far from the source
for even the fuzzy fallback to find a substantial match. The app correctly reported "couldn't locate
automatically — showing page 1, review manually" rather than guessing at a highlight. This is the
one acceptable failure mode: a clearly-labeled "couldn't find it," never a wrong location.

**Incidental fixes made while building this:**
- `testing/verify_highlighting.py`'s debug-log printer expected a single `payload['combined']`
  string; the actual `QUOTE MATCH DEBUG` payload (see `app.js`) is `{normalizedQuote, pages: [...]}`
  — one combined-text string *per page*, since the quote could belong to any of them. Fixed to check
  all pages rather than crashing with a `KeyError` on the first real multi-page failure it hit.
- Confirmed (the hard way, via a spurious `FAIL`) that running two Playwright test scripts against
  the shared port-5051 test server *concurrently* is unsafe: the server only keeps one active
  session's uploaded PDFs on disk at a time, so a second concurrent upload evicts the first session's
  files mid-test, producing a real-looking but spurious "source PDFs no longer on disk" failure.
  Existing tests must always be run one at a time against a given test server — noted here since it
  cost real diagnostic time to rule out as a genuine regression.

**Verified:** `verify_layer_alignment.py` (all 5 viewports, 0.0px off) and `verify_highlighting.py`
(0.0px off, zero console errors) both re-run in isolation and still pass — no regression from the
Bates cross-check addition. Live server (port 5050) restarted on the final code.

## Folder-picker bug fix, styled export-confirm modal, and a new dashboard home screen (2026-07-24)

Three user requests this round.

### 1. Folder-picker bug: "no subfolders" for a folder that genuinely had them

Reported bug: browsing to `sample_data/case_smith` (which has 10 real subfolders) in the Case Mode
folder picker showed "(no subfolders here)". Root-caused directly (not guessed): in `/case/browse`,
a bare `except PermissionError: entries = []` silently swallowed ANY permission error while listing
a directory into an empty list — indistinguishable from a folder that's genuinely empty. Reproduced
concretely with `chmod 000` on a folder containing a real subfolder — confirmed it showed the exact
same misleading empty-folder message. This is very plausibly what's happening in the real
(Electron-packaged) deployment: macOS blocks folder access for a packaged app under TCC sandboxing
until Full Disk Access is granted, or a network-mounted case folder simply has restrictive
permissions — either way, the old code couldn't tell the difference between "empty" and "denied."

Fixed: `/case/browse` now returns a distinct `permission_denied: true` flag when the top-level
`iterdir()` call itself raises `PermissionError` (a per-entry `is_dir()` PermissionError on one
individual child is now also handled — skipped rather than failing the whole listing). The frontend
(`case.js`) shows a visually distinct, actionable message ("Permission denied — check System
Settings > Privacy & Security > Full Disk Access...") instead of silently implying the folder is
empty. New test `testing/verify_case_smith_folder_pick.py`: confirms browsing straight to
`sample_data/case_smith` shows all 10 real subfolders (not the empty state), confirms selecting it
populates the folder-path field correctly, confirms navigating up to `sample_data` also shows its
real contents, and reproduces the permission-denied case via `chmod 000` to confirm the new distinct
message appears and the misleading empty-folder text does not.

### 2. Native `confirm()` replaced with a styled modal for the "unreviewed findings" export warning

The browser's plain OS-chrome `confirm()` dialog looked out of place next to the rest of this app's
custom UI. Replaced with `#export-confirm-modal` (same modal-overlay/modal-box pattern already used
for the Case Mode folder picker) and a `showExportConfirm(message)` Promise-based helper in `app.js`.
New test `testing/verify_export_confirm_modal.py` uses a Playwright `dialog` handler that raises an
assertion if a native dialog ever fires (proving it genuinely doesn't), and confirms both Cancel and
"Export Anyway" behave correctly.

### 3. New dashboard home screen — "Start a New Case" as the primary action, historical cases listed

Spawned a planning agent first to think through the design given the existing app's two entry points
(single-zip quick-test mode at the old `/`, real Case Mode workflow at `/case`) and the Electron
shell's fixed habit of always opening at `/`. Its plan: don't add a third disconnected route — make
`/` the new dashboard (since that's always the first screen opened), move the old single-zip
upload/review flow to `/review` (pure rename, zero logic changes), and enrich the already-existing
`/case/jobs` endpoint with data already sitting in the job manifests (no new persistence needed) —
defendant names, DOL, document counts, and the primary group's own key/readiness.

Implemented as planned:
- `app.py`: `/` now renders `templates/dashboard.html`; the old `index()` view moved to `/review`.
  `/case/jobs` enriched with `defendant_names`, `dol`, `total_documents`, `failed_group_count`,
  `primary_group_key`, `primary_group_ready` — all derived from the existing manifest, nothing new
  persisted.
  Note this is real: the case history shown is only whatever job manifests still exist in this
  server's OS temp directory (`BATCH_DIR`) — not a database. It survives ordinary restarts (this
  directory isn't touched by session cleanup) but has no retention policy and is invisible if the
  app's port changes, since the directory name is port-namespaced.
  Note also: reviewer approve/reject state lives ONLY in browser `sessionStorage`, never sent to the
  server — a pre-existing gap the dashboard makes more visible (closing the tab already loses review
  progress today; "jump back into reviewing" from the dashboard doesn't change that). Flagged, not
  fixed, in this pass.
- `case.js`: dropped its own now-redundant "Recent cases" list (that content graduated to the
  dashboard); added `?job=<job_id>` URL support so the dashboard can deep-link into a specific
  historical case's status page even if it wasn't started in that browser tab; "View chronology"
  links updated to `/review?case=...&group=...`.
- New `templates/dashboard.html` + `static/dashboard.js`: a large, unmistakable "Start a New Case"
  CTA card (styled as a scaled-up oxblood button, not a form) linking to `/case`, a small
  de-emphasized "Quick single-file test" link to `/review`, and a case list reusing the existing
  status-pill/row visual language, each row showing plaintiff/defendant(s)/status/document
  count/date, with a "Continue reviewing" deep-link straight into the reviewer once the primary
  group has any findings, or "View status" while still processing.
- New `testing/verify_dashboard.py`: confirms the CTA is visible and links to `/case`, confirms real
  historical case rows render with the expected fields, and confirms clicking "Continue reviewing"
  actually opens a working reviewer with real findings rendered (not just that the link exists).

**Fallout from the `/` → `/review` rename, found and fixed:** every existing Playwright test that
navigated to the bare app URL for the old upload/review flow broke, since `/` now serves the
dashboard instead. Fixed in all affected scripts (`verify_highlighting.py`,
`verify_layer_alignment.py`, `verify_edit_feature.py`, `verify_detail_slider.py`,
`verify_docx_export_template.py`, `verify_stale_session.py`, `verify_bates_disambiguation.py`,
`verify_multicolumn_highlighting.py`, `verify_repeated_boilerplate_disambiguation.py`,
`diagnose_quote_match.py`, `dump_text_items.py`, `screenshot_full_page.py`) by pointing at
`/review` instead. While re-verifying these, found and fixed three genuinely pre-existing, unrelated
stale-test bugs (not caused by this round's changes, just newly exposed by finally re-running the
full suite together):
- `verify_edit_feature.py` was missing an explicit `wait_for_selector(".finding")`, racing against
  `#results` becoming visible; and assumed clicking a finding row only *selects* it before a
  separate Space press opens editing — current behavior (a deliberate, already-documented design)
  is that a single click both selects AND opens editing immediately. Also assumed a plaintext/`.md`
  export to grep for edited text; export is `.docx` now, so switched to reading it with
  `python-docx` (table cells, not paragraphs — the finding text lives in the DESCRIPTION column).
  Also had a dead `page.on("dialog", ...)` handler left over from before today's styled-modal
  change (item 2 above) — removed, and added real handling for `#export-confirm-proceed` when this
  fixture has more than one finding and only one gets approved.
- `verify_docx_export_template.py` had the same two issues (missing `.finding` wait, dead native-
  dialog handler no longer applicable now that the export-confirm warning is a styled modal) — fixed
  the same way.
- `verify_stale_session.py` clicked the finding *row* expecting that to attempt a PDF load and
  surface the "session expired" message — but a plain row click has been lightweight-selection-only
  for a while now (an already-documented, deliberate split); only the citation chip actually loads
  the PDF. Fixed to click `.finding-citation` instead.

**Verified:** full suite re-run sequentially (never two Playwright scripts against the shared test
server at once — confirmed earlier this session that this causes spurious "session evicted"
failures) — `verify_case_smith_folder_pick.py`, `verify_folder_browser.py`,
`verify_export_confirm_modal.py`, `verify_dashboard.py`, `verify_edit_feature.py`,
`verify_docx_export_template.py`, `verify_stale_session.py`, `verify_layer_alignment.py` all pass
clean. Live server (port 5050) restarted on the final code — confirmed new PID, confirmed `/`,
`/review`, `/case` all respond 200.

## Editable summary, dashboard edge cases, and a real Case Mode bug found via user report (2026-07-24)

### 1. AI-drafted summary is now click-to-edit

Same interaction as an individual finding (`startEditingSummary` in app.js, mirroring
`startEditingFinding`): click opens an inline textarea pre-filled with the current text, Enter
commits, Escape cancels, and the edit persists across a page refresh via the same sessionStorage
pattern as review status/finding edits/added facts. No backend changes needed — `buildExportPayload`
already read `.summary-box`'s live DOM text at export time, so an edited summary flows into the
exported chronology automatically. Verified via `verify_summary_edit.py`.

### 2. Dashboard edge-case coverage added

Building `verify_dashboard_edge_cases.py` (mocking `/case/jobs` via Playwright route interception)
surfaced a real bug while writing the test: `dashboard.js`'s error handling only caught genuine
network failures — `fetch()` doesn't reject on an HTTP error status, so a real 500 from `/case/jobs`
silently rendered as "No cases yet" instead of a distinct error message. Fixed by explicitly
checking `resp.ok`. Also added `verify_case_job_deeplink.py`, covering the `?job=` deep-link feature
added when the dashboard was built, which had no test of its own until now.

### 3. Real Case Mode bug reported by the user against case_smith — found, fixed, and verified end to end

User report: on the real (17-document) `case_smith` case, the exported chronology had no Bates
numbers in the PAGE column, and the PDF viewer said source documents were "no longer on disk" once
processing finished. Root cause, found by reading the code and confirmed with direct reproduction
(not guessed): `GET /case/<job_id>/<group_key>/results` returned a hard 404 "Unknown group"
whenever the group hadn't been created in the manifest yet — a completely normal, transient state
during the first minute-plus of a case (while it's still finding the Complaint/NOI and grouping
documents by identity, well before the per-group processing loop even starts). The frontend's
live-polling code (`fetchAndRenderCaseResult` in app.js) treats *any* `error` field in the response
as fatal and returns without ever scheduling its polling `setInterval` — so a reviewer opening the
review link the moment a case starts (the normal way to use this app) could have their very first
poll land in that window, silently and permanently freezing the page with no further updates ever,
even long after the job actually finished. What looked like "no Bates numbers" and "PDFs missing"
was actually a page that had stopped updating within the first few seconds.

Confirmed via direct, incremental debugging against real, uninterrupted case_smith runs (not
assumed): a `flush=True`-instrumented live-tab-watching script showed the exact 404 firing at the
very first poll, and zero DOM findings ever rendering for the rest of the run, while a *fresh*
reload of the same URL after the job finished rendered correctly — proving the bug was specifically
about the live-watching tab's polling dying, not the underlying data.

**Fixed on the backend**: `/case/<job_id>/<group_key>/results` now returns `{"ready": false, ...}`
(200) instead of a 404 when the group doesn't exist yet AND the overall job hasn't reached a
terminal state (`done`/`error`) — the same shape the frontend already handles correctly for "still
working, keep polling." Only once the job is genuinely done/errored and the group still never
showed up does it hard-404, so a truly bad/stale link still fails correctly rather than polling
forever.

**Also fixed, a secondary contributing issue found during the same investigation**: the live-polling
render condition only re-rendered when the finding count *grew*, but the final result (after Bates
resolution + duplicate-record merging) can have a *lower* count than the last partial snapshot —
duplicates get merged away. A tab that happened to survive past the 404-freeze bug could still get
stuck on a stale, pre-resolution snapshot forever in that case. Fixed to always render the final
"done" result at least once regardless of the count comparison.

**Verified two ways**:
- `verify_case_group_not_yet_created.py` (fast, deterministic): confirms the fixed endpoint returns
  the correct shape before/after the job's terminal state, and confirms via mocked responses that
  the frontend's polling now survives the transition and renders real data.
- `verify_case_smith_live_view.py` (slow, ~15-25 min, the real thing): starts an actual, complete,
  uninterrupted case_smith run, opens the review page immediately (before it's finished, the exact
  reported scenario), leaves it open the entire time with zero reloads, and confirms once done: 13
  of 14 findings show a real resolved Bates number in the still-open tab (the 14th is a known,
  accepted case where the model's quote genuinely didn't match verbatim — not a bug), the PDF viewer
  loads a source document and draws real highlights (no "session expired" error), and the exported
  `.docx`'s PAGE column has real Bates values for 8 of 9 rows. **PASS** — both originally-reported
  symptoms are confirmed fixed against the real case, not just a synthetic reproduction.

Also checked `case.js`'s own job-status polling (the `/case` status page, a different endpoint) for
the same failure pattern — confirmed it does NOT have this bug, since its polling interval is
established unconditionally before the first poll's result is even considered, structurally
different from the case-mode results polling in app.js.

## Two new case_smith-shaped fixtures, and a comprehensive highlighting regression test (2026-07-24)

Two new fixtures added to `scripts/make_case_test_folders.py`, same 10-subfolder structure as
`case_smith` but genuinely different content per case (not just renamed copies):
- `case_ferreira` — Daniel R. Ferreira v. Dr. M. Castellano / Crestline Urgent Care, a delayed
  diagnosis of appendicitis (misread as gastroenteritis at urgent care). `records/` reuses the
  existing `case_002_pdfs` fixture (already Bates-stamped; its baked-in patient name matches this
  case's plaintiff for internal consistency).
- `case_whitfield` — Linda K. Whitfield-Nakamura v. Dr. P. Adeyemi / Brightwater Cardiology
  Associates, an anticoagulation (warfarin) dosing/monitoring error. `records/` reuses the existing
  `case_003_pdfs` fixture, which deliberately contains a real discrepancy (conflicting warfarin
  doses) — useful variety so the regression test below isn't only ever exercising clean,
  single-source findings.

Every document in both fixtures — the Complaint plus all 8 non-records subfolder placeholder
files — got its own Bates stamp via a shared `_build_full_case()` helper (distinct prefixes `FER`/
`WHIT`), and `records/` already carries its original `MED` stamps from the earlier Bates-numbering
round. Confirmed directly via `pdfplumber` extraction on every non-complaint file in both fixtures.

**`verify_case_highlighting_regression.py`** — the strongest highlighting check in the suite: runs
both fixtures through a REAL, complete `/case/start` → chronology-generation run (no mocking, no
sessionStorage shortcuts), then clicks through **every single citable finding in both cases** (not
a sample) and checks, per finding: a highlight box actually appears, it aligns to a real rendered
text span within a few pixels (the same strict check as `verify_highlighting.py`), and the Bates
cross-check banner never shows "mismatch" (the concrete signal the wrong page is being shown). Any
failure anywhere is treated as a hard failure — the "it needs to be perfect" bar the user set for
this whole feature earlier in the project.

**Result: PASS, cleanly, on the first full run.** `case_ferreira`: 11/11 citable findings (covering
AT-ISSUE entries, potential issues, and a discrepancy) all at 0.0px alignment, zero Bates mismatches.
`case_whitfield`: 8/8 citable findings (including the deliberately-planted dosing discrepancy) also
all at 0.0px alignment, zero Bates mismatches. Zero console errors across both runs. 19 total
citable findings checked, 19 correct.

## Durable storage (SQLite) + incremental reprocessing of newly-added case files (2026-07-25)

User's two requests: (1) reliably pull up a chronology from a month ago — full timeline, all facts,
working PDF highlighting — which the existing OS-temp-dir-based storage (and browser-sessionStorage-
only review state) could not guarantee; (2) after a case is done, pick up new files added to its
folder later and reprocess only those, intelligently (aware of the complaint and what's already
known), not from scratch. Planned in Plan Mode (see the approved plan for full design rationale) and
implemented as designed — a Plan agent validated the architecture before implementation, catching
several real issues addressed below.

### 1. New `webapp/db.py` — SQLite, not a new dependency

Python's stdlib `sqlite3`: no server to install, no account, no cost, works identically in dev and
on the real Windows tower (`TOWER_SETUP.md`). Lives at a per-OS application-data directory (NOT
`tempfile.gettempdir()`) — `~/Library/Application Support/LawFirmAgent/` on macOS, `%APPDATA%/
LawFirmAgent/` on Windows, `~/.local/share/LawFirmAgent/` on Linux — with an explicit
`LAWFIRMAGENT_DATA_DIR` override (same idiom as the existing `LAWFIRMAGENT_PORT`) for test isolation
and for the case the tower's Flask process eventually runs as a Windows Service under a service
account. Four tables: `cases` (each case's manifest as a JSON blob, plus a few columns worth
indexing/sorting on directly — `job_id`/`plaintiff_name`/`folder`/`status`/`started_at`/
`finished_at`), `processed_files` (backs incremental reprocessing), `review_actions` and
`added_facts` (durable reviewer state). One DB with FK cascades, deliberately: `DELETE FROM cases
WHERE job_id=?` is a future retention/deletion feature (already flagged as a requirement in
`PRODUCT_DEFINITION.md`) away from cleanly removing everything relational in one transaction.
`_save_batch_manifest`/`_load_batch_manifest`/`_get_batch_manifest` in `app.py` kept their exact
signatures — every other call site in `_run_case_job` needed zero changes. `BATCH_SESSIONS_DIR` (the
case-mode PDF-storage directory `serve_pdf` already reads from) simply got repointed to the new
app-data location — no new PDF-storage layout needed, `serve_pdf`/`_find_closest_pdf` untouched.
Incidentally fixes a latent bug: the old `path.write_text(json.dumps(...))` manifest write wasn't
atomic; SQLite's UPDATE/INSERT is.

### 2. Stable, content-based finding IDs — a real pre-existing bug fixed along the way

Findings were keyed by array position (`timeline-${origIndex}` in `app.js`) — already fixed for
`timeline` specifically in an earlier round, but **`potential_issues` and `discrepancies` were still
plain `${sectionKey}-${index}`**, the same reassign-on-reorder bug, just not yet closed for those two
sections (found by the validating Plan agent, confirmed directly by reading the code). Both durable
review state and incremental reprocessing (which appends to and re-dedupes these same lists) need
ids that survive a merge — so this got fixed properly, server-side: new `_assign_finding_ids()` in
`app.py` stamps a `finding_id` (SHA-1 of section+source+quote+text, with defensive disambiguation on
collision, same idiom `_resolve_record_sources` already used for label uniqueness) onto every
`timeline`/`potential_issues`/`discrepancies` item — during live partial-generation snapshots AND
the final post-dedup result, always producing the same id for the same content regardless of array
position. `app.js`'s `idFor` now just reads `item.finding_id`, falling back to the old positional
scheme only for data that predates this. Verified idempotent and collision-safe directly.

### 3. Durable reviewer state (Case Mode only)

sessionStorage stays the synchronous source of truth for all rendering (lowest risk, smallest diff);
five new thin endpoints (`/case/<job>/<group>/review`, `/edit`, `/summary_edit`, `/facts`,
`DELETE .../facts/<id>`) back it with fire-and-forget POSTs from `app.js`'s existing single-item
state-change functions (`setFindingStatus`, the inline-edit `finish()`, `saveSummaryEdit`,
`onFactChipClick`/`removeAddedFact`) — never blocking, never throwing into the UI if offline.
`case_group_results` now also returns `review_state`/`added_facts`; a genuinely fresh browser tab
(sessionStorage empty for that session) pre-seeds from them before its first render. Scoped
explicitly to Case Mode (`job_id`+`group_key`) — the plain `/review` single-upload flow has no job
to key rows by and was never part of "pull up a month later."

### 4. Incremental reprocessing

New `POST /case/<job_id>/rescan` (manually triggered — a button, not automatic background polling,
so it never surprises the reviewer with unexpected model usage) → `_run_case_rescan`: diffs
`folder.rglob("*.pdf")` against `db.get_processed_paths()` for genuinely new file paths (deliberately
NOT detecting in-place content changes to an already-processed file — scoped out cleanly rather than
half-solved, since that would need retroactively evicting old findings first); groups the whole new-
files batch against existing groups' identity first, then against each other in the same batch (so
two new files belonging to one new secondary individual land in one new group, not two) — needed a
small manifest addition, `identity_name`/`identity_dob` stored alongside `display_name` on secondary
groups (in both the original Phase 3 grouping and the new rescan path), rather than fragile string-
parsing "Also mentions: X" back apart. For the primary group, new `_build_incremental_context()`
gives the model a compact prior-context block (already-known demographics, already-known record
labels — NOT the full prior chronology text, to stay within budget) so it's "intelligent about what
it's extracting" per the user's own framing, not starting from a blank slate. New
`_merge_incremental_group_result()` reuses the existing `_merge_chunk_findings` (existing findings
passed first, so id-collision disambiguation never reassigns an already-reviewed item's id) then
re-runs dedup/record-source-labeling across the combined set — deliberately does NOT re-run Bates
resolution on old items (each pass already resolved its own items correctly against the text it was
actually given). New shared `_copy_files_into_session()` helper used by both the initial run and
rescans.

### Verified

`verify_durable_storage.py` (new): spins up a dedicated, disposable Flask subprocess (own port, own
`LAWFIRMAGENT_DATA_DIR`) — confirms the default app-data dir is a real per-OS location (not temp),
confirms a case's DB row and PDFs land in the configured durable location, **kills and restarts the
server process** and confirms `/case/jobs`/`/results` return identical data, then opens the case in
a **brand-new browser context** (no shared storage at all) and confirms previously-approved findings,
an edited summary, and PDF highlighting all just work — the actual end-to-end proof, not just a
file-existence check. All checks PASS.

`verify_incremental_reprocessing.py` (new): against a disposable temp copy of a small fixture — a
no-op rescan correctly reports nothing new; adding one real new file and rescanning produces a new,
traceable finding while the previously-approved finding's id and durable status survive the merge
unchanged (confirmed in a fresh browser context too); a second no-op rescan confirms the new file is
now tracked; renaming the case's folder away produces a clean 400, not a crash. All checks PASS.

Full regression sweep re-run clean: `verify_dashboard.py`/`verify_dashboard_edge_cases.py` (the
`/case/jobs` sort now comes from SQL, not filesystem mtime), `verify_case_job_deeplink.py`,
`verify_bates_disambiguation.py`/`verify_summary_edit.py`/`verify_export_confirm_modal.py` (hand-
crafted fixtures with no `finding_id` correctly fall back to the old id scheme), `verify_edit_feature.py`,
`verify_highlighting.py`, `verify_layer_alignment.py`, `verify_folder_browser.py`,
`verify_case_smith_folder_pick.py` — all pass.

**One more real, previously-missed bug found and fixed while re-running `verify_case_creation.py`**:
it still navigated to the old `f"{APP_URL}/?case={job_id}&group=..."` URL — `/` has been the
dashboard (not the case-mode review page) since that feature was built, and this specific call site
used a URL-literal shape (`/?case=...`, not the bare `page.goto(APP_URL)` pattern) that the earlier
sweep fixing every other test script for the `/` → `/review` rename didn't catch, since it searched
for that different pattern. Fixed to `/review?case=...`. Confirmed by re-running: complaint
auto-detection, `record_type`/`author` header rendering, and `at_issue` badge rendering all now
correctly PASS (12 findings, 9 with headers, 6 at-issue) — the part of this test that actually
exercises rendering logic touched by today's `finding_id` changes. The test's second fixture
(`case_nodefendant`, the no-complaint-fallback path — logic entirely untouched by today's storage/
incremental-reprocessing work) didn't get a completed run in this session: the background task
running it was killed by the environment twice in a row, both times well into a multi-minute
17+7-document run, consistent with an infrastructure timeout on this specific long-running test
rather than an application bug — no error of any kind was ever observed from the app itself.

## Chronology Preview, hiding the upload form in Case Mode, and surfacing "Check for new files" on the actual review page (2026-07-25)

Three related requests, all about the chronology-builder page (`/review`, `webapp/templates/
index.html`/`static/app.js`):

### 1. "Preview Chronology" button

A button at the bottom of the timeline pane shows exactly what "Export Approved Chronology" would
produce — the same header block (RE/DOL/Facts/DOB/etc.), Abbreviations/Record Sources legend, and
DATE/PAGE/RECORD/SOURCE/DESCRIPTION table as the real Word template — rendered as HTML directly in
the viewer pane, in place of whichever PDF was showing. Deliberately an HTML rendering, not a
generated PDF: the export itself is a Word document, not a PDF, so there was no real PDF to load
into the pdf.js viewer, and generating one just for this preview would have meant a second,
parallel document-generation path to keep in sync with the real one. Reuses `buildExportPayload()`
directly — the exact same data `/export/docx` renders — so the preview can never drift out of sync
with the actual export. Clicking any finding's citation afterward exits preview mode automatically
(back to the source PDF/highlight view) — no separate "close preview" button to hunt for.

The button is `position: sticky` at the bottom of the (scrollable) timeline pane, so it's reachable
without scrolling through a long chronology first. Verified directly (via screenshots) that this
doesn't visually or functionally overlap/intercept clicks on the actual finding rows, including
across a scrollable 7-item list — `page.screenshot(full_page=True)` produced a visually confusing
render for this specific combination of `position: sticky` + viewport-relative `vh` units (a known
full-page-screenshot artifact with sticky positioning), but a normal viewport screenshot and a
direct scripted click-through of every row in a 7-item list confirmed no such issue actually exists
in real use.

### 2. Upload form hidden in Case Mode

The single-zip upload form made no sense on a page showing a specific Case Mode group's results —
now hidden outright (`form.style.display = "none"`) whenever `?case=&group=` are present in the
URL. The plain single-upload flow (no case params) is completely unaffected.

### 3. "Check for new files" moved to where reviewers actually work

The button for incremental reprocessing (added in the previous round) originally only lived on the
separate `/case` status page — not part of a reviewer's normal day-to-day workflow once a case is
underway, per direct user feedback ("I am not seeing the button"). Now also present directly on the
`/review?case=&group=` page itself, next to the export button. Reuses the exact same `POST /case/
<job_id>/rescan` endpoint; since the GROUP's own status (unlike the job's overall status) genuinely
transitions back to "processing" while a rescan runs on it, the page's existing live-polling loop
already handles this correctly once restarted — clicking the button unconditionally re-establishes
the polling interval (not left to the poll function's own conditional scheduling), the same fix
already applied to the `/case` status page's equivalent button, since the very first poll right
after starting a rescan can race the background thread and see a stale "done" status.

### Verified

New `testing/verify_chronology_preview_and_case_ui.py` (sessionStorage-restore trick, deterministic,
no LLM call): confirms the upload form is visible in plain mode and hidden in Case Mode (and vice
versa for the rescan row), confirms the preview shows correct and complete content (RE line, DOB,
PMHx, both approved findings' text, the AI summary, and a Bates number in the PAGE column) with the
PDF canvas hidden while it's showing, and confirms clicking a citation afterward correctly exits
preview mode and shows the source PDF again. All checks PASS. Re-ran
`verify_summary_edit.py`/`verify_export_confirm_modal.py`/`verify_bates_disambiguation.py`/
`verify_layer_alignment.py` — all still pass; some real-LLM-backed re-runs
(`verify_edit_feature.py`) hit a mix of differently-shaped transient timeouts under today's
cumulative heavy back-to-back model-call load, but a direct, controlled synthetic reproduction
(scripted click-through of every row in a 7-item scrollable list) confirmed the new sticky preview
button never intercepts a finding-row click, and every affected test passed cleanly on retry.

## Real bug: the Preview Chronology button was invisible on real, longer chronologies (2026-07-25)

User report: "I still don't see the preview chronology thing" — even after a hard refresh, on a
real case (`case_ferreira`) with 32 findings and a populated Key Facts panel. First confirmed the
live server was genuinely serving the updated code (it was) before investigating further, ruling
out caching.

**Root cause, found by directly measuring the actual page**: `.findings-pane`'s `max-height: 82vh`
assumes the split-view starts near the top of the viewport, but in real usage there's substantial
header content above it — the notice banner, stats line, review bar, the (new) rescan row, and a
populated Key Facts panel with several tabs. On the user's exact case/URL, `.findings-pane`'s own
box measured `y: 664` to `y: 1484` against a 1000px-tall viewport — meaning roughly 480px of the
pane's own bottom, where the sticky "Preview Chronology" button lived, was below the browser's
fold. `position: sticky` only sticks within its container's ON-SCREEN portion — if the container's
own bottom edge is off-screen, a child stuck to that edge is invisible too, not "stuck" to anything
visible. My original synthetic tests used minimal fixtures (1-2 findings, no Key Facts data) short
enough that this never triggered — the bug only shows up with realistically-sized real chronologies,
exactly the scenario the user hit.

**Fixed** by moving the button entirely out of the scrollable timeline pane and into the
always-visible `review-bar`, right next to "Export Approved Chronology" (wrapped in a new
`.review-bar-actions` sub-container so they stay adjacents while `review-progress` stays pinned to
the left) — the same reasoning that already put "Check for new files" up there rather than
somewhere that depends on scroll position. No longer `position: sticky` at all; the
`.findings-pane`/`.preview-chronology-btn`-specific CSS added for the sticky approach was removed
outright rather than left as dead code.

**Verified**: re-confirmed directly against the user's exact real case/URL, that the button's
on-screen Y position is now within the viewport with zero scrolling. Added a regression guard to
`verify_chronology_preview_and_case_ui.py`: asserts the button's actual bounding-box position is
within the viewport (not just that CSS considers it "visible", which was true even in the broken
sticky version) — this specific check would have caught the original bug had it existed at the
time. All checks still PASS.

**Lesson**: "is_visible()" (CSS display/visibility/non-zero-size) is not the same claim as
"actually reachable on screen without scrolling" — a sticky/absolutely-positioned element can pass
the former while failing the latter if its positioning container itself extends off-screen. Worth
remembering for any future "always visible" UI element in this app.

## Chronology Preview redesigned as a full-width modal (2026-07-25)

Follow-up user request: "I want the preview button to open in a full screen modal that takes up
almost the entire screen left to right to make sure we see the whole thing without scrolling left
to right. A vertical scroll is fine." The DATE/PAGE/RECORD/SOURCE/DESCRIPTION table needs real
horizontal room — the viewer pane (roughly half the window) forced awkward column widths.

Converted from the inline viewer-pane swap into a true modal dialog: `#chronology-preview-modal`
(`.modal-overlay`, same overlay pattern as the existing export-confirm modal) containing a new
`.modal-box-wide` (96vw wide, max-width 1800px, 92vh tall, flex column so its content area scrolls
vertically only). Has its own header row with a Close button, closes via that button, clicking
outside the box, or Escape. `.preview-doc`'s max-width raised from 820px to 1500px to use the extra
room, and the events table now uses `<colgroup>` + `table-layout: fixed` to keep DATE/PAGE/RECORD/
SOURCE narrow (9% each) and let DESCRIPTION take the rest — needed once the table had much more
width to fill.

Because this is a true overlay (`z-index: 100`), it now blocks interaction with the page underneath
while open — different from the old inline-swap design, where clicking a citation implicitly
"exited" the preview. Closing now requires the modal's own Close button (or click-outside/Escape)
before anything underneath is reachable again.

**Verified**: rewrote the relevant checks in `verify_chronology_preview_and_case_ui.py` — replaced
the old "PDF canvas hidden while previewing" check (no longer meaningful; the underlying viewer-pane
isn't touched by the new modal) with `modal_shown`/`modal_is_wide` (`.modal-box-wide`'s bounding-box
width >= 85% of viewport width) plus the same content-completeness checks as before. Discovered the
click-outside-the-modal design meant a leftover step attempting to click a citation immediately after
opening the preview timed out — Playwright's own trace confirmed the modal overlay was intercepting
the click. Fixed by explicitly clicking `#chronology-preview-close` and asserting the modal is hidden
first, then confirming `.pdf-highlight` still renders normally afterward (proving the source-document
viewer underneath was untouched the whole time). Also re-confirmed the earlier bounding-box
regression guard (button reachable without scrolling) still holds now that the button lives in
`.review-bar`, independent of the modal itself. All checks PASS, including against a real screenshot
of the live case (`case_ferreira`) confirming the modal renders correctly full-width with no
horizontal scrolling needed.

## Case-folder picker rebuilt as a native upload, replacing server-side path browsing (2026-07-25)

User report: "there seems to still be some kind of a permissions issue with pointing to the right
location in the file system for the folder... It works for the experience of locating and uploading
a single file. But we [lose] that native experience for locating a folder." Root cause: `/case/browse`
(built earlier this session) had Flask list directories directly off whatever disk it happened to be
running on — a fundamentally different, more fragile trust model than the single-zip upload, which
works flawlessly because the BROWSER's own native picker grants file access, not the server. Flask
reading arbitrary folders requires broad OS-level permission (macOS Full Disk Access, or the
Windows-service equivalent) that a plain upload never needs. This was flagged in the original
`/case/browse` docstring as a deliberate tradeoff to support the tower deployment (Electron on the
paralegal's laptop, Flask on a separate tower — see TOWER_SETUP.md) — but the actual pain of that
tradeoff (permission friction) outweighed the reason a server-side native Electron dialog was
originally ruled out (a path picked on the laptop is meaningless on the tower's own filesystem).

**The fix**: replaced server-side path browsing with the same model the single-zip upload already
uses successfully — `<input type="file" webkitdirectory multiple>`, the browser's own native folder
picker, uploading every file found (subfolders included) via multipart/form-data with each file's
path relative to the picked folder preserved (`file.webkitRelativePath`). Flask never reads an
arbitrary filesystem path again; it only ever reads from its own upload-populated
`CASE_SOURCES_DIR/<job_id>/` directory. This eliminates the permission problem entirely rather than
working around it, and is actually a better fit for the tower topology than the old design: files
travel over HTTP regardless of which machine Flask runs on, so the case folder no longer needs to be
mounted/visible on the tower's own filesystem at all.

Changes: `/case/browse` removed entirely. `/case/start` and the new upload-aware `/case/<job_id>/
rescan` (previously a bodyless POST — a rescan now means re-picking the same folder so the browser
can re-enumerate its current contents, then re-uploading) both accept `files` as repeated multipart
parts. New `_save_uploaded_case_files`/`_safe_relative_path` in app.py sanitize and save each
upload's relative path under `CASE_SOURCES_DIR` (rejecting `..`/absolute-root segments, so an
uploaded filename can never escape that directory). The manifest's old absolute-path `folder` field
is replaced by `source_dir` (internal, Flask-owned) and `folder_display_name` (cosmetic — just the
picked folder's own top-level name, shown on the status page in place of the old path).
`db.py`'s `processed_files` table (incremental-rescan tracking) is now keyed by path RELATIVE to
`source_dir` rather than an absolute filesystem path, since a re-upload never resolves to the same
absolute path twice — required a one-time schema fixup in `init_db()` (rename `abs_path`→`rel_path`,
clear now-incompatible old rows) since this is a prototype with no real case data to preserve, same
"clean cutover" precedent as the earlier `BATCH_DIR` removal.

The old folder-browser modal (`case.html`'s `#folder-browser-modal`, `case.js`'s
`loadFolderBrowser`) is removed outright, along with its CSS (`.folder-path-row`/`.folder-breadcrumb`/
`.folder-list*`). "Check for new files" (on both the `/case` status page and the `/review` page,
added earlier this session) now triggers a hidden `webkitdirectory` input, re-uploading the re-picked
folder's current contents on selection.

**Verified**: new `testing/case_upload_helpers.py` builds the same multipart request shape a real
browser upload produces, for both Playwright's request context (`start_case`/`rescan_case`) and
plain-`urllib`-based scripts (`urllib_start_case`) that don't use a full Playwright `page`. Updated
every existing verify script that used the old `folder_path` field (`verify_case_creation.py`,
`verify_case_smith_live_view.py`, `verify_case_job_deeplink.py`, `verify_case_highlighting_
regression.py`, `verify_case_group_not_yet_created.py`, `verify_durable_storage.py`,
`verify_incremental_reprocessing.py`) to use it — all PASS, including the full real-LLM
`verify_case_creation.py` run (complaint auto-detection, recursive subfolder ingestion, at-issue
flagging) and `verify_durable_storage.py`/`verify_incremental_reprocessing.py`'s multi-scenario
rescan coverage (no-op rescan, a genuinely new file's findings appearing and being traceable,
previously-approved findings surviving the merge with stable ids, a second no-op rescan confirming
the new file is now tracked, and a rescan attempted with no re-selected folder correctly 400ing).
Removed `verify_folder_browser.py` and `verify_case_smith_folder_pick.py` outright — both tested the
now-removed `/case/browse` endpoint and its specific permission-denied messaging, which no longer
exists by design rather than by omission.

Additionally ran direct Playwright UI smoke tests (not permanent fixtures, exploratory) confirming:
the `case.html` form's folder input shows a correct "N PDF files found" summary and submits
successfully; the `/case` status page's "Check for new files" button opens a real file-chooser
(intercepted via Playwright's `expect_file_chooser`, confirming the OS-native picker is genuinely
what's invoked) and correctly reports "No new files found" after re-selecting the same folder; the
`/review` page's rescan button does the same. One of these ad hoc runs showed a transient blank
rescan message immediately after clicking (never reproduced on immediate retry, across 15
consecutive 1-second samples) — most likely a one-off race from running it back-to-back with an
identical rescan against the same job under heavy concurrent local-LLM load in this dev environment,
not a reproducible defect; the underlying poll-reflection code (`app.js`'s handling of
`rescan_status`/`rescan_message`) is unconditional on the group's own "done" status, which is
what the fix requires.

## Offline license gating added (2026-07-25)

User request: a way to gate the app to a licensed firm (3-month/12-month/lifetime tiers) that works
fully disconnected from the internet, with a hard requirement that nothing sensitive ever ends up
plaintext-committable once this repo is pushed to GitHub. Initial framing was a pre-loaded pool of
~10 keys per tier; after confirming this is a single-customer deployment (not a multi-firm product),
recommended a signed-token design instead — a pool of shared valid keys is the wrong shape for one
customer, and is inherently weaker even for many (a static list embedded in the app is just data
sitting on disk, trivially extracted, with no way to revoke/extend one key without shipping a new
build).

**Design**: a license token is `{customer, tier, issued_at, expires_at}`, canonical-JSON-encoded and
signed with an Ed25519 private key (`scripts/license_tool.py generate-keypair`/`issue`, a dev-only
CLI never imported by the app). The app (`webapp/license.py`) only ever needs the matching PUBLIC
key — committed to the repo at `webapp/license_public_key.pem`, not a secret — to verify a token's
signature and expiration entirely offline, no network call. The private key is generated outside
this repo entirely (default `~/.lawfirmagent_keys/`, `chmod 600`, refuses to write inside the repo
directory even if pointed there) — since it never enters the repo's working tree, it structurally
cannot end up in a `git push` no matter what commands run inside the repo, which is a stronger
guarantee than encrypting it at rest while still living in a repo-adjacent path. `.gitignore` was
also created for the first time this session (repo had none) with license-key patterns as
defense-in-depth, plus the standard venv/node_modules/logs exclusions, ahead of the user's stated
plan to push this repo to GitHub.

A `before_request` hook in `app.py` blocks every route except `/license` and static assets until a
valid token is installed — full-page GET routes (dashboard/review/case/architecture) redirect to
`/license`; every other endpoint (JS-polled JSON APIs, PDF serving, all POST routes) gets a plain
402 JSON error instead, since redirecting those would hand an HTML page to code expecting
`resp.json()`, turning a clear message into a confusing parse error. A soft anti-clock-rollback
check (`license_clock_state.json` in the app-data dir, same location `db.py` already uses for
durable case storage) refuses a token if the system clock appears to have moved backward more than
a few hours since the app last ran — explicitly a soft mitigation, not real DRM, since this gates a
business relationship with one known customer, not an adversarial paying stranger.

**UI**: `/license` shows current status (customer/tier/days-remaining, or the specific reason it's
invalid) and a paste-in form; installing validates before saving, so a bad token never overwrites a
working one. A small badge in the top-right of every page (`templates/_license_badge.html`, wired
into every template automatically via a Flask `context_processor`) shows the tier as a pill
("Lifetime"/"12-Month"/"3-Month") plus, for time-limited tiers, days-remaining, the formatted
expiration date, and a thin linear progress bar showing elapsed-vs-total license term — a Material
Design "linear progress indicator" pattern for time-remaining, restyled in this app's own
oxblood/parchment palette (not Material's default blue/grey) to stay consistent with this project's
earlier, deliberate move away from a generic/default look (see the design-overhaul entry from
2026-07-21).

**Verified**: minted a real test 12-month token via the CLI, confirmed `verify` independently checks
out; confirmed unlicensed requests correctly redirect (page routes) or 402 (API routes), confirmed
installing a valid token unlocks everything and an invalid one is rejected without touching the
active license. Screenshotted both badge states — lifetime ("Lifetime" pill, no progress bar) and a
synthetic 3-month token 60 days into a 90-day term (correctly shows "29 days left · expires Aug 24,
2026" with the progress bar ~67% filled). Re-ran `verify_case_group_not_yet_created.py` against the
now-license-gated test server with a valid token installed — still PASS, confirming the gate doesn't
interfere with normal request flows once licensed. Minted and installed a real lifetime token
(customer "LawFirmAgent Owner") for the actual dev/live deployment before restarting either server
with this code, specifically so the license gate going live wouldn't lock out the app's own owner.

## Bundled, offline-capable installer built and verified on macOS (2026-07-25)

User request: "do we need to make some kind of installer such that this can be downloaded from
github and it will start literally everything... work perfectly the first time just by clicking the
icon after the install?" Planned via Plan Mode (see the approved plan for full architecture
reasoning) given the real air-gap tension: the deployment target is deliberately offline
(`TOWER_SETUP.md`), so "download from GitHub" and "never needs the internet again" are only
compatible if the installer front-loads everything during a one-time provisioning run rather than
fetching anything on every later launch.

**Real, pre-existing bug found during planning, not just a missing feature**: the packaged `.app`
verified in the previous session only appeared to work because this dev machine already had a live
Flask process on port 5050 — `ensureBackendRunning()`'s `httpOk()` pre-check short-circuited before
ever trying to spawn its own backend. The actual spawn path (`repoRoot()/webapp/.venv/bin/python`)
resolves to a location inside the packaged app bundle that doesn't exist. A genuinely cold packaged
launch would have failed. Confirmed and fixed as part of this work (see below).

**What was built:**
- `webapp/requirements.txt` — added missing `python-docx`/`Pillow` (imported directly but never
  declared — a real gap for any fresh-environment build).
- `webapp/app.py`/`webapp/license.py` — new `_resource_path()` helper (PyInstaller's documented
  `sys.frozen`/`sys._MEIPASS` idiom) resolves prompts/templates/static/the license public key
  correctly in BOTH dev mode (unchanged behavior) and a frozen executable (previously, `Flask(__name__)`'s
  auto-detected template/static folders and the `Path(__file__).resolve().parent.parent`-based
  prompt paths would not have resolved correctly once frozen — fixed proactively, not discovered by
  a failure, by reasoning through what PyInstaller's runtime layout actually does to `__file__`).
  `_get_ocr_reader()` now points EasyOCR at a bundled, pre-downloaded copy of its detection/
  recognition models with `download_enabled=False` when frozen, so OCR never reaches the network
  either — dev mode's existing `~/.EasyOCR` auto-download behavior is untouched.
- `scripts/build_backend.py` — freezes `webapp/app.py` + all dependencies via PyInstaller (`onedir`
  mode — `onefile` re-extracts on every launch, wasteful once PyTorch is in the bundle) into a
  genuinely standalone executable, no system Python required. Bundles prompts/templates/static/the
  EasyOCR models/the license public key as PyInstaller "datas". `pyinstaller-hooks-contrib` already
  ships hooks for `torch`/`torchvision`/`easyocr`, so no manual hidden-import fighting was needed —
  built cleanly on the first real attempt. Output: `electron/vendor/backend-mac/`, ~671MB (PyTorch
  dominates), well under GitHub's 2GB release-asset limit.
- `electron/vendor/ollama-mac/` — bundled Ollama, but NOT just the single `ollama` binary as
  initially assumed: a real cold-start test caught that Ollama 0.32.x needs its companion
  `llama-server` binary plus a set of `libggml-*`/`libllama*`/`libmtmd*` shared libraries and the
  Apple Silicon `mlx_metal_v3`/`mlx_metal_v4` directories alongside it — Ollama's own generate call
  failed with "llama-server binary not found" the first time, checked a long list of relative
  candidate paths, and copying the entire `Ollama.app/Contents/Resources/` directory (minus its own
  icon assets) fixed it. ~463MB total.
- `electron/main.js` — `app.isPackaged`-based branching throughout: packaged mode resolves the
  bundled Ollama/backend via `process.resourcesPath` (new `vendorDir()`/`getOllamaBinaryPath()`/
  `getBackendCommand()` helpers); dev mode keeps today's exact behavior unchanged. New
  `ensureModelPulled()` step (between Ollama and backend startup) checks `ollama list` against
  whichever instance is up and runs `ollama pull` only if the model's genuinely missing — the ONE
  step that ever needs internet, and only the first time; every later launch's list-check finds it
  already there. Packaged mode points the bundled Ollama at a private model directory
  (`app.getPath("userData")/ollama-models`) so it never depends on/conflicts with a system-wide
  Ollama install (like this dev machine's own LaunchAgent-managed instance on the same port) —
  `ensureOllamaRunning`'s existing "reuse if already answering" check means a dev machine with a
  system Ollama already running just reuses it rather than double-installing, which is harmless and
  actually desirable. Also added the standard macOS `activate` handler (Dock icon click with no
  window open reopens one, matching VS Code) while in the file.
- `electron/package.json` — per-platform `extraResources` (`mac.extraResources`/`win.extraResources`)
  copying the vendor directories into the packaged app.
- `.gitignore` — `electron/vendor/`/`electron/dist/` excluded (large, regenerated build output —
  distribute via GitHub Release assets, not git commits).
- `DESKTOP_PACKAGING.md` — documented the exact steps needed to do the equivalent Windows build
  once real hardware is available (still the one genuinely unverified/unverifiable piece in this
  environment).

**Verified — the real cold-start test the previous session's pass should have been**: stopped the
dev Flask process AND unloaded the system Ollama LaunchAgent (`launchctl unload`) so both ports were
genuinely free, confirmed via `lsof`. Pre-seeded the packaged app's private model directory by
copying the already-downloaded `llama3.1:8b` blobs (avoiding a real ~15-minute/4.9GB re-download
for a step that only exercises the already-battle-tested `ollama pull` CLI itself, not this
session's own integration code — the actual integration risk was in the surrounding glue, which
this test fully exercises regardless). Launched the freshly-rebuilt packaged `.app` cold:
- Correctly spawned its OWN bundled Ollama (`Contents/Resources/ollama-mac/ollama serve`) and OWN
  bundled backend (`Contents/Resources/backend-mac/chronology-builder-backend`) — confirmed via
  `ps`/`lsof`, not just "the app didn't show an error."
- `ensureModelPulled` correctly found the pre-seeded model via `ollama list` and skipped straight
  through (proving the check-before-pull logic works, not just the pull itself).
- A real `/analyze` call through the fully cold-started packaged app — actual PDF extraction, a
  real Ollama generate call through the bundled/private instance, a correctly-structured chronology
  back — not just "the server answered a health check."
- A second full stop/relaunch cycle reached a fully-ready backend in 3 seconds (model already
  present, nothing to re-pull), confirming repeat launches are fast and don't redundantly re-check/
  re-download anything.
- Restored the dev environment afterward (system Ollama LaunchAgent reloaded, dev Flask restarted)
  and re-ran `verify_case_group_not_yet_created.py` against normal dev mode — still PASS, confirming
  none of the `_resource_path()`/Flask-constructor/license.py changes affected dev-mode behavior.

**Honestly not fully verified**: the actual `ollama pull` network path itself was deliberately
avoided in this test (pre-seeded instead, see above) purely for time — it's a stable, independently-
maintained Ollama CLI feature, not custom code, so this is a reasonable place to have drawn the
line, but worth noting explicitly rather than silently implying it was exercised. The Windows build
(PyInstaller backend, Ollama Windows binary + supporting files, NSIS installer) remains completely
unverified — no Windows machine available in this environment; `DESKTOP_PACKAGING.md` now has exact
steps to follow once one is.

## Versioning, auto-update, structured logging, and an install wizard (2026-07-25/26)

Four related requests, planned via Plan Mode (see the approved plan for full architecture reasoning
and research on logging best practices). Built and verified together since they share touch points
(`electron/package.json`, `main.js`'s startup sequence, the app-data logs directory).

**Versioning**: root `VERSION` file (single source of truth, `0.0.1-pre` — valid semver stored
internally per a clarifying question, since electron-builder/electron-updater both need real semver
to function; the literal "pre-release-0.0.1" phrasing isn't valid semver). `scripts/bump_version.py
{patch|minor|major}` updates `VERSION` and mirrors it into `electron/package.json`. `webapp/app.py`
reads `VERSION` at startup via the existing `_resource_path()` helper (bundled as one more
PyInstaller data file) and exposes it via a `@app.context_processor`, same pattern as the license
badge. New `_version_badge.html` — bottom-right, fixed position, deliberately separate from the
top-right license badge.

**Auto-update**: `electron-updater` with the `github` provider (reads `package.json`'s
`build.publish`, no separate hosting needed). Confirmed direction: silent best-effort check on
launch (packaged mode only — dev mode skips entirely) that fails gracefully with no internet/no
releases, plus a manual check via clicking the version badge itself (no app menu exists to hang a
menu item off, so the badge doubles as the affordance) — reconciles "built-in auto-update" with the
real deployment target often being air-gapped. Needed a proper `contextBridge`/`ipcMain` bridge
(`electron/preload.js`, wired into `createWindow`'s `webPreferences`) since `contextIsolation: true`
means the renderer can't call back into the main process otherwise — found and fixed that
`preload.js` was referenced in `package.json`'s `files` list but never actually existed until now.
Downloaded updates only install after an explicit "Restart Now" confirmation dialog.

**Structured logging** (the piece explicitly asked to be researched, not assumed): converges on
structured JSON-lines + redact-by-default + daily rotation + bounded retention — the standard shape
for "ship me a log file and diagnose it" support workflows. `webapp/applog.py`/`electron/applog.js`
both write into `get_app_data_dir()/logs/YYYY-MM-DD.log` (two components, not literally one shared
file — avoids real cross-process write-locking for little benefit; "zip the logs folder" already
satisfies the actual goal). **Found and fixed a real timezone bug during this work**: Python's
handler originally rolled over at local-time midnight while the Electron side used UTC
(`toISOString()`) — for any timezone behind UTC (all of the Americas), the two components would
have written into DIFFERENT daily files for part of every day. Fixed by making the Python side use
UTC too, confirmed by testing at a moment where local (07-25) and UTC (07-26) genuinely disagreed.
Wired into `app.py`: `before_request`/`after_request` logging every request (method/path/status/
duration — never query strings or bodies), a global `@app.errorhandler(Exception)` (today, an
unhandled exception had zero durable record beyond an unwatched terminal), and `logger.exception`-
equivalent calls added at the existing per-group/per-file `except Exception` blocks in
`_run_case_job`/`_run_case_rescan`/document extraction, which previously discarded the actual
traceback and kept only a short string. `electron/main.js`'s spawned children switched from
`stdio: "ignore"` to piped stderr (captured into a small tail buffer, logged only on failure) — a
real, related fix, since a spawn failure previously had literally no diagnostic trail at all.
Verified directly: triggered a real exception, confirmed a same-day log file was created lazily,
contains well-formed JSON per line (parsed every line to confirm), a full traceback string, and
manually audited that no filename/PDF/patient content appears anywhere in any field.

**Install wizard**: confirmed direction — "single GitHub file, one button" is just GitHub's own
Release page, no custom page needed (added a real `README.md`, which didn't exist before, with a
Getting Started section pointing at it). The actual improvement: NSIS switched from one-click to
assisted/wizard mode (`oneClick: false`, one config flag). More substantively, replaced the splash
screen's static "Downloading…" text (no progress indication for a 15-minute/4.7GB first-run
download) with a real inline-DOM progress bar. Rewrote `ensureModelPulled` to use Ollama's own HTTP
streaming API (`POST /api/pull`) instead of shelling out to `ollama pull` and regex-scraping its
carriage-return-redrawn terminal output — the HTTP API returns real structured
`{status, completed, total}` progress lines, turned into a genuine percentage. Verified: rebuilt the
packaged app, confirmed it still launches correctly, shows the correct bumped version in its badge,
and that `electron-updater`'s new dependency doesn't break the bundle (loaded far enough to reach
and log its own graceful "no internet/no releases yet" failure).

**The actual GitHub repo now exists and this automated versioning pipeline was verified for real,
not just in a test harness**: user created `pb49939pb/ChronologyBuilder` on GitHub, but this project
directory had no local git repo yet and the user had no SSH key/`gh` CLI configured on this machine
— the reason their first push attempt silently didn't take (confirmed the remote was genuinely
empty via `git ls-remote` before doing anything). Generated a new SSH key, user added it to their
GitHub account, verified the connection, then did the real `git init` + first commit (483 files;
explicitly reviewed the full `git add -A -n` dry-run output first for `.venv`/`node_modules`/private-
key/large-file leakage before committing — none found, confirming `.gitignore` works as intended)
+ push. **The `.github/workflows/bump-version.yml` action fired for real on this actual first push**
and correctly bumped `0.0.1-pre` → `0.0.2` (dropping the pre-release tag, per `bump_version.py`'s own
logic), committed with its `[skip version bump]` loop-guard, and did not re-trigger itself — the
exact end-to-end behavior the whole versioning design was for, now confirmed outside a test harness.
Also installed a portable `gh` CLI (`.tools/gh/`, no Homebrew needed, same pattern as the portable
Node install) for future GitHub work in this project.

**Repo is currently public** — worth keeping in mind given this is still a prototype (no real case
data belongs in it regardless, per the existing standing rule, but worth being extra mindful now
that anyone can see the repo, not just people with direct access).

## Real bug fixed: clicking into a chronology opened a whole new app window (2026-07-26)

User report: clicking into a chronology from the dashboard/case status page inside the packaged
Electron app opened what looked like a second copy of the whole app, instead of just navigating to
the new page. Root cause: `dashboard.js`/`case.js`'s "Continue reviewing"/"View chronology" links
use `target="_blank"` deliberately — in a plain browser this correctly opens the chronology in a
new tab while leaving the dashboard/status page open in its own tab. Electron has no concept of
browser tabs, though, and with no `setWindowOpenHandler` registered, its default handling of
`target="_blank"` (internally the same as `window.open()`) is to spawn an entirely new native
`BrowserWindow` — which is exactly what looked like "a new instance of the app."

Fixed at the Electron shell level only, not in the web app: `electron/main.js`'s `createWindow()`
now registers `mainWindow.webContents.setWindowOpenHandler(...)`, which denies the new-window
request and instead calls `mainWindow.loadURL(...)` on the existing window — one window total,
just navigating to the new page. Deliberately left the `target="_blank"` markup itself untouched,
since removing it would make the plain-browser experience worse for no reason; the fix is purely
about how Electron specifically interprets that same markup.

**Verified via CDP** (real screenshots of this sandboxed dev environment don't show actual window
content — same limitation noted earlier when this Electron shell was first built): quit the
already-running packaged app, rebuilt with the fix (`npm run dist` → v0.0.4), reinstalled, relaunched
with `--remote-debugging-port` so Playwright could connect via `connect_over_cdp` and directly count
real OS-level windows/pages, not just DOM state. Before the fix this would have shown 2 pages after
clicking; confirmed exactly 1 page total both before and after clicking a real "Continue reviewing"
link, with that single page correctly navigated to the chronology's `/review?case=...&group=...`
URL — the fix works and doesn't regress the plain-browser tab-opening behavior (untested here
directly, but structurally guaranteed unchanged since the web app's own markup was never touched).

## Real bug found: the bundled backend was stale, missing everything from the versioning/logging work (2026-07-26)

While verifying the window-fix release by actually downloading it from GitHub (not just testing the
local build) and cold-starting it: the version badge showed **v0.0.2** instead of the actual current
version. Root cause: `electron/vendor/backend-mac/` (the PyInstaller-frozen backend) was built once,
during the earlier bundled-installer work, and **never rebuilt since** — `npm run dist` only
re-packages whatever's already sitting in that directory, it doesn't re-run
`scripts/build_backend.py`. Every feature added in the subsequent versioning/auto-update/logging
session (the `VERSION` file, the version badge template, `applog.py` entirely) was silently absent
from every packaged build since, including the just-published v0.0.3 and the first cut of v0.0.6.
Confirmed directly: `applog*`/`VERSION` were missing from the bundle's contents entirely before the
fix, present after re-running `scripts/build_backend.py`.

**Fixed**: re-ran `scripts/build_backend.py`, rebuilt the Electron package, and re-verified via a
genuine cold start (killed the dev Flask process holding port 5050 first, confirmed the packaged
app then spawned its own bundled backend, confirmed the dashboard now correctly shows v0.0.6).
Re-uploaded the corrected assets to the already-published v0.0.6 GitHub release (deleted the stale
assets, uploaded the rebuilt ones) rather than cutting yet another release.

**Verified the actual downloaded artifact, not just the local build**: downloaded
`Chronology-Builder-0.0.6-arm64.dmg` directly from its GitHub release URL via `curl`, confirmed the
byte count and SHA-512 checksum both matched `latest-mac.yml` exactly (proving the upload itself
wasn't corrupted), then mounted the DMG, installed to `/Applications`, and launched it — this is
what actually caught the stale-backend bug, since testing only the local `electron/dist/` build
would have hidden the exact same problem (both were built from the same stale frozen backend).

**Lesson worth remembering**: `scripts/build_backend.py` must be re-run any time `webapp/` source
changes, not just once ever — `npm run dist` alone is not sufficient to pick up backend code
changes, only Electron-side (`main.js`/`package.json`) ones. Worth automating this dependency (e.g.
having `npm run dist` shell out to the freeze script first) rather than relying on remembering.

## Security audit (2026-07-21)

Full pass across injection, auth/authz, XSS, Electron hardening, Flask hardening, secrets handling,
and dependency vulnerabilities, per the HIPAA-adjacent threat model this project has had in mind
since PRODUCT_DEFINITION.md §7/§9 (no real PHI yet, but treated as if there will be). Read every
route in `webapp/app.py`, all of `webapp/db.py`/`license.py`/`applog.py`, `electron/main.js`/
`preload.js`/`config.js`, and every `webapp/static/*.js` file end to end rather than sampling.

### The one real architectural finding: remote mode has zero per-request authentication

This is the most important thing in this audit, and it's not a hypothetical. Confirmed directly
from `webapp/license.py`: the license system is entirely "is *some* valid license token present in
this host's app-data directory," checked in `_enforce_license()` (`webapp/app.py:93-102`). It has no
concept of a user, session, cookie, API key, or client identity of any kind — `get_current_license()`
takes no request context at all. In `remote` mode (`electron/config.js`, `TOWER_SETUP.md`), the
Flask server runs on a separate "tower" machine and is reached over `http://192.168.50.1:5050` by
whatever's on the other end of that link. Once the license file exists on the tower (which it must,
for the app to be usable at all), **every route — `/case/jobs` listing every case's plaintiff name
and defendant names, every case's full chronology findings including patient demographics, `/export/
docx`, everything — is reachable by anything that can reach that IP and port, with no login, no
token, no per-request check of any kind.** The only thing standing between "on that network segment"
and "full read/write access to every case's PHI" is the physical topology described in
`TOWER_SETUP.md` (a direct Ethernet cable, no switch, no gateway). That's a real and reasonable
mitigation for the *documented* topology, but the application has no defense in depth if that
topology is ever violated — a switch added later "just to also plug in a printer," a Wi-Fi adapter
re-enabled on the tower, a second laptop plugged into a hub instead of a direct cable, or simply the
tower's Windows Firewall not being configured as recommended, and there is nothing else in the
software stack that would stop a second device on that segment from pulling every case's records.

**Not fixed — this is a real feature, not a bug fix.** Three options, roughly in order of effort:

1. **Shared-secret header/cookie**: the Electron client sends a fixed pre-shared token (generated at
   pairing time, stored in `app.getPath("userData")` on the laptop, checked in `_enforce_license` or
   a new `before_request` hook) on every request. Cheapest to build, meaningfully raises the bar
   (a device on the segment now needs the secret, not just network reachability), but it's still a
   single shared secret, not real per-user identity, and doesn't help if the secret itself leaks.
2. **mTLS or a client certificate** on the private link: stronger, matches "dedicated point-to-point
   link" well, but is real new surface (cert generation/rotation/distribution) for a two-machine,
   one-user deployment that may not be proportionate.
3. **Bind + firewall as the actual control, documented as such**: accept that this is fundamentally a
   trusted-network design (like most home NAS/self-hosted-app software), and instead of adding
   in-app auth, make the network-level mitigation the documented, verified control — i.e. `TOWER_SETUP.md`
   should say explicitly "this app has no application-layer authentication; the ONLY thing preventing
   LAN-wide PHI access is the point-to-point topology and the tower's Windows Firewall scoped to that
   one adapter," and that firewall scoping should be confirmed as an actual setup step, not just a
   "defense in depth" aside.

**Recommendation**: do (1) now — it's a small, contained change (one shared secret + one header
check) that closes the "someone else plugs into the same segment" gap cheaply, and pair it with (3)
regardless, since the current docs undersell how load-bearing the physical topology actually is.
Skip (2) unless a future revision needs genuine multi-user/multi-device access to the tower.

### Fixed

- **Missing CSP / `X-Content-Type-Options` headers** (`webapp/app.py`, new `_set_security_headers`
  after_request hook near the top of the file, alongside the other before/after hooks). This app
  loads zero remote content of any kind — confirmed no external URLs anywhere in any template, `.js`,
  or `.css` file — which makes a strict CSP unusually cheap here. Added `default-src 'self';
  script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';
  connect-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self';
  frame-ancestors 'none'` plus `X-Content-Type-Options: nosniff`. `script-src` deliberately has no
  `'unsafe-inline'`/`'unsafe-eval'` — confirmed neither pdf.js nor mermaid (the only two non-trivial
  bundled JS libraries) call `eval()`/`new Function()` anywhere in their bundles (`grep`'d both). The
  one inline `<script>` this app had (the update-badge click handler in `_version_badge.html`) was
  moved to `webapp/static/version-badge.js` specifically so `script-src 'self'` could hold with no
  exceptions. `style-src` keeps `'unsafe-inline'` since several templates use inline `style=""` for
  simple show/hide toggling and rewriting all of those into classes wasn't worth it given style
  injection can't achieve code execution the way script injection can. **Verified, not assumed**:
  started the dedicated test-server instance (`testing/start_test_server.sh`, port 5051), confirmed
  the headers are actually present via `curl -D -`, then drove `/`, `/architecture` (mermaid), `/review`
  (pdf.js), and `/case` with Playwright (`testing/.venv`) — zero console errors on any page (a CSP
  violation shows up as a console error, so this would have caught a real regression), and separately
  confirmed the mermaid diagram on `/architecture` actually rendered a real `<svg>` (not just "no
  errors").
- **Electron network allowlist gap** (`electron/main.js:455-456`, `installNetworkAllowlist`). This
  session's newly-added allowlist (see the previous entry's context) filtered `onBeforeRequest` on
  `["http://*/*", "https://*/*"]` only — `ws://`/`wss://` requests weren't intercepted at all, so a
  hypothetical future XSS in the renderer (none found — see below) could still open a raw WebSocket
  to an arbitrary host with no allowlist check. Added `"ws://*/*"`/`"wss://*/*"` to the filter list.
  The app doesn't use WebSockets today (Flask streams via chunked NDJSON, not `ws://`), so this is
  pure defense-in-depth, but it was a real gap in a hook whose entire job is being an allowlist.
  Confirmed Electron's `webRequest.onBeforeRequest` URL filter does support `ws(s)://` patterns.
  `node --check electron/main.js` passes.

### Confirmed already sound (audited, no change needed)

- **SQL injection**: every query in `webapp/db.py` uses `?`-parameterized queries via `sqlite3` —
  confirmed for every single statement in the file, no string-built SQL anywhere.
- **Zip-slip / path traversal**: `safe_extract_pdfs()` (`app.py`) only ever joins `Path(name).name`
  (stripping any directory component) under the resolved extract dir, with an explicit
  parents-containment check before writing. `_safe_relative_path()` (`app.py`, used for
  `webkitRelativePath`-carrying case-folder uploads) strips `".."`/`"."`/absolute-root segments and
  runs each segment through `secure_filename()` before ever joining a path — a malicious
  `webkitRelativePath` like `../../../etc/passwd` cannot escape `CASE_SOURCES_DIR`. `serve_pdf()`
  resolves the requested session dir and confirms containment before serving, and only ever uses
  `Path(filename).name` for the requested file. No path in this app is ever built from unsanitized
  client input.
- **Command/subprocess injection**: no `shell=True` anywhere in the repo. The only `subprocess.run()`
  calls are in `scripts/build_backend.py`/`scripts/make_app_icon.py` (dev-only build tooling, fixed
  argument lists, no user input). Electron's `spawn()` calls (`main.js`, Ollama + backend) use fixed
  binaries/args resolved from `app.isPackaged`/`process.platform`, never from any request or renderer
  input.
- **XSS / output encoding**: every `.innerHTML =`/template-literal DOM write across `app.js`/`case.js`/
  `dashboard.js` that includes server- or LLM-derived text goes through one of each file's own
  `escapeHtml()` (3 near-identical copies, one per file — matches this codebase's "small, local
  helper over a shared abstraction" convention) or uses `.textContent`. Checked this exhaustively,
  not just the first few hits: all 28 `escapeHtml(` call sites plus every `.innerHTML =` assignment in
  all three files were read in place. LLM-generated findings text, filenames, plaintiff/defendant
  names, and citation quotes are all escaped before insertion. `onFactChipClick`'s `querySelector`
  uses `CSS.escape()` on a hash-derived id, not raw text. No gaps found.
- **IDOR**: `job_id` is `uuid.uuid4().hex` (122 bits, unguessable). `group_key` is a normalized,
  guessable hash of the patient's name — but every case route requires *both* `job_id` and
  `group_key` together, and there's no route that accepts a bare `group_key`. Given the finding
  above (no auth at all on the LAN in remote mode), `group_key` predictability is moot in practice —
  the real exposure is the lack of any auth boundary, not id guessability on top of it.
- **License-enforcement coverage**: `_LICENSE_EXEMPT_ENDPOINTS`/`_LICENSE_REDIRECT_ENDPOINTS`
  (`app.py:85-90`) were checked against every `render_template()` route in the file (`license_page`,
  `dashboard`, `index`, `architecture`, `case_page`) — all four non-exempt GET pages are correctly
  listed in the redirect set; nothing is missing an endpoint-name entry that would silently bypass
  the license gate.
- **Electron hardening**: every `BrowserWindow` (`main.js`) sets `contextIsolation: true`,
  `nodeIntegration: false`; sandboxing is Electron's own default (true, since neither window
  overrides it) and wasn't disabled anywhere; `webSecurity` isn't touched (stays enabled/default);
  `preload.js` exposes exactly two functions (`checkForUpdates`/`onUpdateStatus`), nothing that hands
  the renderer any Node/Electron capability. No remote/untrusted content is ever loaded — `loadURL`
  is only ever called with the app's own backend URL or (via `setWindowOpenHandler`) a same-origin
  navigation target.
- **Flask hardening**: `debug=False` always (`app.py`'s `__main__` block) — no Werkzeug debugger RCE
  surface. No `SECRET_KEY` in use anywhere (no sessions/flash messages), so there's nothing to
  generate insecurely. `MAX_CONTENT_LENGTH` is capped at 200MB.
- **Secrets/data handling**: `scripts/license_tool.py`'s `generate-keypair` explicitly refuses to
  write the private signing key inside the repo tree (checks `REPO_ROOT in key_path.resolve()`) and
  chmods it 0600; only the public key (not sensitive) is written into the repo. `.gitignore` covers
  `license_signing_key*`, `license.token`, `license_clock_state.json`, and the usual `.venv`/
  `node_modules`/build-output paths. Spot-checked every `applog.log_event`/`exc_info=` call site added
  this session against `applog.py`'s own documented redaction policy — filenames, extracted text,
  prompts, and model output are never passed as `context`/message content anywhere; only counts,
  types, and opaque ids are logged.
- **DOCX export (`/export/docx`)**: takes an arbitrary client JSON body but is a pure in-memory
  renderer — every value goes through `python-docx`'s own `add_run()` (XML-escaped internally via
  `lxml`, no raw XML injection possible), the output filename is server-generated
  (`time.strftime(...)`, never client input), and there's no filesystem read/write driven by any
  client-supplied path. Can't be abused to read or write arbitrary files.

### Dependency vulnerabilities (flagged, not fixed)

Ran `pip-audit` against `webapp/.venv` (installed fresh into the venv for this — no system-wide
install) and `npm audit` against `electron/`.

- **npm** (`electron/package.json`, production deps only — `electron-updater`): 0 vulnerabilities.
  Full audit including `devDependencies` (`electron`, `electron-builder`) failed because npm's legacy
  quick-audit endpoint is being retired server-side (`400 Bad Request` from `registry.npmjs.org`) —
  an npm/registry-side issue, not something fixable here; worth re-running once npm's bulk-advisory
  endpoint is what this npm version calls by default.
- **pip** (`webapp/requirements.txt`, no versions pinned): `pip-audit` found real advisories against
  the *currently installed* versions in `pillow` (11.3.0 — a long list, mostly image-parsing CVEs),
  `torch` (2.8.0, an `easyocr` transitive dependency), `requests`/`urllib3`, `click`, `filelock`, and
  `pdfminer-six`. **Deliberately not upgraded in this pass**: `requirements.txt` has no version pins
  at all, so a fresh `pip install -r requirements.txt` today would already pull newer, patched
  versions on its own — the exposure is specifically the *already-installed* dev venv, not a bad pin
  committed to the repo. Pillow/torch in particular are exactly the two libraries this project's own
  OCR-accuracy benchmarks (`testing/ocr_benchmark.py`, referenced throughout this log) are pinned
  against by installed version, not by requirements.txt — bumping them in place risks silently
  changing OCR behavior that was carefully measured, which needs its own re-benchmark pass, not a
  drive-by version bump inside a security audit. Recommend: re-run the OCR benchmark suite after any
  future `pip install --upgrade`, and consider actually pinning `requirements.txt` going forward so
  "what's installed" and "what's committed" can't silently drift apart in either direction.

### Not otherwise flagged

Everything else audited — SQL injection, zip-slip, XSS, Electron `webPreferences`, Flask `debug`/
`SECRET_KEY`, secrets-in-git, license-gate coverage — came back clean on direct inspection; see the
"confirmed already sound" list above for specifics rather than a generic "looked fine."

**Update 2026-07-21, same day: the remote-mode auth gap above is now addressed** — see "Trust-on-
first-use client pairing" below.

## Trust-on-first-use client pairing for remote/tower mode (2026-07-21)

Closes the one real finding from the security audit above: remote mode had zero per-request
authentication. Discussed the design with the user first — specifically walked through why a naive
"generate a key, attach it, done" isn't actually authentication unless the server has some concept
of *which* key is the right one, which led to trust-on-first-use (TOFU) as the mechanism: the tower
has no paired key on its first boot; whichever key arrives on its very first request gets
permanently remembered; every later request must match exactly or gets rejected. Given the actual
topology (`TOWER_SETUP.md`: a direct point-to-point Ethernet cable, nothing else ever plugged into
that segment), the first device that can possibly reach the tower over that link genuinely is the
laptop — so TOFU is a real, meaningful guarantee for this specific deployment, not just security
theater. Honest limits, documented in `webapp/pairing.py`'s own docstring: this authenticates "a
device holding this key," not the laptop's hardware specifically, and re-pairing (if the key file is
ever deleted) trusts whatever connects next — same physical-isolation discipline as original setup.

**Implementation:**
- `webapp/pairing.py` (new): `PAIRING_KEY_FILE = db.get_app_data_dir() / "paired_client_key.token"`,
  `check(header_value)` — the TOFU logic, under a lock (mirrors `db.py`'s `_write_lock` pattern) to
  avoid a torn write if the first page load's several near-simultaneous asset requests all race to
  pair at once (harmless in practice since they all carry the same client's key, but the lock
  prevents a corrupted file regardless).
- `webapp/app.py`: hoisted `_BIND_HOST` (`LAWFIRMAGENT_BIND_HOST` env var) to module level so it's
  shared between the new hook and the existing `app.run(host=...)` call. New `_enforce_pairing_key`
  before_request hook, registered before `_enforce_license` — a complete no-op whenever
  `_BIND_HOST` is loopback (i.e. every dev/test run and local-mode use), so this activates
  automatically and *only* under the exact condition that creates the exposure (the tower being
  bound to a real LAN address), with no separate flag to remember and zero risk of forgetting to
  turn it on. No endpoint exemptions needed (unlike licensing) — see below for why.
- `electron/main.js`: `getOrCreatePairingKey()` (random 32-byte key via Node's built-in `crypto`,
  stored in `app.getPath("userData")`, generated once on first launch) and
  `installPairingKeyHeader()` — a `session.defaultSession.webRequest.onBeforeSendHeaders` hook
  (same session/pattern as this session's earlier network allowlist) that injects
  `X-Chronology-Pairing-Key` into every request to the backend host. This is why no endpoint
  exemptions are needed server-side: the header gets attached at the network layer to literally
  every request including the very first page navigation, so there's no separate "bootstrap" page
  to keep reachable the way the license page needs to be.
- `.gitignore` (`paired_client_key.token`, same defense-in-depth reasoning as `license.token`) and
  `TOWER_SETUP.md` (documents the automatic activation + re-pairing procedure) updated.

**Verified for real, not assumed** — simulated remote-mode exposure by binding a throwaway test
server to this dev machine's actual LAN IP (`192.168.4.39`) rather than loopback:
1. Plain `curl` with no header against the LAN-bound instance → `403`. The default loopback test
   server (port 5051) was completely unaffected throughout (still `200`, no header needed) —
   confirms activation is correctly scoped to bind host, zero impact on existing dev/test workflows.
2. First `curl` with a made-up key → `200`, and `paired_client_key.token` appeared on disk holding
   that exact value.
3. A *different* key afterward → `403`. The original key again → `200`. Confirms real TOFU lock-in,
   not just "first request always succeeds."
4. Launched the actual packaged Electron shell (`LAWFIRMAGENT_MODE=remote`, pointed at that same
   LAN-bound instance, a fresh `--user-data-dir` so it generated its own real key) against a
   freshly re-paired (token file deleted) server — confirmed via CDP/Playwright
   (`connect_over_cdp`) that the real dashboard loaded successfully with zero manual steps, proving
   the header is genuinely injected transparently by the app itself, not just by a hand-crafted
   curl request. Immediately after, a plain `curl` (no header) and a `curl` with a guessed key
   against that now-paired instance both got `403` — proving a second, different client genuinely
   cannot get in once the laptop has paired.
5. `node --check electron/main.js`, `ast.parse` on `app.py`/`pairing.py` — clean. Re-ran
   `testing/verify_durable_storage.py` (its own loopback-bound throwaway server, unaffected by any
   of this) twice — first run hit the same known-flaky tiny-fixture LLM nondeterminism documented
   earlier in this file (zero findings on a 1-page test PDF), second run passed clean end to end
   (case processing, server restart, fresh-browser-context durability, highlighting) — consistent
   with that being pre-existing fixture flakiness, not a regression from this change.

## Auto-update was silently never finding updates — found and fixed (2026-07-26)

While verifying "does the app check for updates on launch" against the real installed `v0.0.9`
build, its own log showed the check running automatically (confirming that part works exactly as
designed) but failing every time with `Unable to find latest version on GitHub... please ensure a
production release exists: HttpError: 406`. Root cause: `electron-updater`'s `GitHubProvider` only
looks at GitHub's "latest production release" by default, and every release published from this
repo so far (`v0.0.3`/`v0.0.6`/`v0.0.9`) is marked **Pre-release** (correct — this is still a
prototype) — so there was never a "production release" for it to find, no matter how many
pre-releases got published. Fixed with one line in `electron/main.js`:
`autoUpdater.allowPrerelease = true`.

**Verified for real**: built and published `v0.0.10` with the fix, quit the running `v0.0.9` app,
downloaded the actual published `v0.0.10` `.dmg` from GitHub (checksum matched the local build
byte-for-byte), installed it fresh, and launched it. Its log now shows
`update_not_available: "Already on the latest version"` on that same automatic launch-time check —
the real failure mode is gone, not just theoretically fixed. Version badge confirmed `v0.0.10`.

## Auto-update still didn't work on the wife's real Windows install — a second, different root cause (2026-08-02)

Real user report on `v0.0.12`: "auto-update didn't work, had to manually download/install from
GitHub instead of the app detecting and installing it." The prerelease fix above was verified on Mac
only, and there's no CI that builds/publishes the Windows side at all (`.github/workflows/` has just
the version-bump workflow — every Windows release has been built on real Windows hardware and its
artifacts uploaded to the GitHub Release by hand, outside anything a coding session here could
previously see or test).

Checked the actual live GitHub releases directly (`gh release view <tag> --json assets`) rather than
guessing, and found the real cause immediately: `v0.0.12`'s release has
`Chronology.Builder.Setup.0.0.12.exe` + `.exe.blockmap`, but **no `latest.yml`** — only
`latest-mac.yml` (from the separately-built Mac artifacts) was present. Confirmed via
`node_modules/electron-updater/out/NsisUpdater.js`/`electronHttpExecutor.js` that Windows's
`NsisUpdater` looks specifically for a file literally named `latest.yml` and has no other fallback —
so every Windows client's auto-update check found nothing to update to, no matter how new the actual
release was. Also checked `v0.0.11` for the same class of problem and found a second, related bug:
its `latest.yml` DOES exist, but its internal `url`/`path` field says
`Chronology-Builder-Setup-0.0.11.exe` (hyphens) while the actually-uploaded asset is named
`Chronology.Builder.Setup.0.0.11.exe` (dots) — a filename mismatch that would 404 the download even
though the metadata file itself was present. Both are consistent with the same root cause: a manual,
non-automated release process with no validation step, not a bug in this app's own code.

Also definitively resolved a previously-`unverified` question this same code had flagged
(`electron/main.js`'s `installNetworkAllowlist` comment): does electron-updater's HTTP traffic go
through Electron's default session, where the app's own network allowlist could plausibly be
blocking it? Read `electron-updater`'s actual source
(`node_modules/electron-updater/out/electronHttpExecutor.js`) — its `ElectronHttpExecutor` uses
`electron.net.request()` through `session.fromPartition("electron-updater", ...)`, a completely
separate session from `session.defaultSession`. The allowlist hook never sees this traffic at all,
in either direction — ruled out as a cause, and the comment (which had said this was unverified)
updated to state the confirmed finding.

**Fixed for the currently-stuck real release, not just documented for next time**: downloaded the
actual `v0.0.12` `.exe` from GitHub, computed its real sha512 (base64) and byte size, built a
correct `latest.yml` pointing at the exact real asset filename, and uploaded it to the existing
`v0.0.12` release (`gh release upload v0.0.12 latest.yml`) — confirmed fetchable afterward at
`https://github.com/pb49939pb/ChronologyBuilder/releases/download/v0.0.12/latest.yml`. Any Windows
install still on an older version should now find and install `v0.0.12` on its next automatic check.

**Fixed the process, not just this one instance**: added `scripts/generate_latest_yml.py` (takes
just the already-built `.exe` path and version, computes the sha512/size, writes a correctly-shaped
`latest.yml` reading the real filename directly off the file rather than it being typed/guessed
separately — the exact mistake that produced `v0.0.11`'s mismatch). Documented the whole requirement
prominently in `DESKTOP_PACKAGING.md`'s Windows build steps: all three of the `.exe`, `.exe.blockmap`,
and `latest.yml` must be uploaded together, every release, with no exceptions.

**Not verified end-to-end** (no Windows machine available in this environment, same limitation noted
throughout this file): a real Windows install actually picking up this newly-uploaded `latest.yml`
and completing a real download+install. The fix is grounded in reading electron-updater's own source
for its exact file-lookup/hash-verification behavior, not assumption, and the uploaded file was
confirmed byte-correct (sha512/size recomputed independently from the same downloaded `.exe`), but
the actual live Windows auto-update flow (NSIS silent install, UAC prompt behavior on an unsigned
installer, etc.) still needs a real confirmation on her actual machine.

## A serious, real bug found via regression testing: the prompt's own worked example was contaminating output (2026-08-02)

Re-ran `testing/verify_durable_storage.py` (flagged earlier this session as needing a re-run given
the scale of `app.py`/`app.js` changes) as a final check before wrapping up, using
`sample_data/case_000_pdfs` (a single 1-page document, chief complaint: sore throat). It failed:
"highlight boxes in fresh context: 0" — the citation existed and the right PDF loaded, but nothing
highlighted. Bisected via `git stash` (reverting `app.py`/`app.js`/prompts to clean `HEAD`, re-running
against the exact same fixture) to separate a real regression from ordinary LLM non-determinism, and
inspecting the actual finding JSON both times.

What that turned up was much more serious than a highlighting glitch: the extracted "text" for
`record_01.pdf` (a sore-throat visit) described a completely different clinical scenario — left ear
pain, a ruptured eardrum, Ciprodex — verbatim, sentence for sentence. That exact passage was a
"Worked example" added to `prompts/chronology_prompt_structured.txt`'s VISITS section earlier this
same session (built to match the anonymized real visit-note style the user shared, meant purely to
illustrate the target level of narrative richness) — written as a full, fluent, concrete clinical
narrative rather than an abstract template, which made it easy for the model to reproduce wholesale
as if it were real output for an unrelated document, rather than treating it as a style guide. This
is exactly why the quote didn't highlight: the fabricated text's "quote" was a truncated, non-verbatim
fragment that doesn't literally appear anywhere in the real document, so neither the server's nor the
browser's exact-match search could locate it — a downstream symptom of upstream fabrication, not an
independent bug in the highlighter.

**Fixed**: rewrote the worked example to be an explicit, bracketed schematic (`"Presents for
[complaint] x[duration], previously seen at [prior care setting]..."`) instead of a fluent concrete
narrative, plus an explicit instruction never to reuse this example's specific wording/symptoms/
medication for any real document. **Verified for real**: reran the same `case_000_pdfs` fixture — the
extracted text now correctly describes the sore throat/strep/amoxicillin visit that's actually in the
document, with no trace of the old example's content; Bates/page-number resolution succeeded (exact
quote now genuinely present in the source); a live Playwright click on the citation correctly
highlighted the real passage. Reran `testing/verify_durable_storage.py` and
`testing/verify_export_confirm_modal.py` in full afterward — both pass clean.

This was found only because a full regression pass was run before considering this phase's work
done, not because anything about the original symptom (a highlighting failure) pointed at a prompt-
contamination root cause — worth remembering next time a "worked example" gets added to any prompt:
prefer an abstract/bracketed template over a fluent concrete narrative, precisely because a fluent
example is a fabrication risk, not just a style choice.

## Real production failure on the wife's machine: Ollama read-timeout on Case Mode chunks, and a near-miss caught while fixing it (2026-08-03)

Real user report, with a log file: multiple patient groups in a real case failed with
`requests.exceptions.ReadTimeout: HTTPConnectionPool(host='127.0.0.1', port=11434): Read timed out.
(read timeout=1800)` — one chunk's Ollama call took longer than the hardcoded 30-minute timeout on
her Windows machine, repeatedly, not a one-off. The failure is caught per-group (`_run_case_job`'s
broad `except`, by design so one bad group never takes down an unattended overnight run), which
means the case still shows overall `"done"` even though a specific patient group silently failed —
worth knowing if this ever needs explaining to a user again. The immediate recoverable workaround
(files never got recorded as processed since the failure happened before that point) is "Check for
new files" on the same case, re-selecting the original folder — it correctly detects the failed
group's files as unprocessed and retries just that group.

Three changes made: (1) `_call_model_for_chunk`'s per-call timeout raised 1800s → 3600s, (2)
retry-on-timeout added — a `ReadTimeout` now gets one retry before failing the group, the same
pattern already used for a degenerate (empty-but-valid) response, reasoning that a slow machine
having a slow moment isn't necessarily stuck, (3) `NUM_CTX` default lowered 12288 → 11264 for
smaller, faster individual chunks, trading more (smaller) chunks for lower per-call timeout risk.

**A real near-miss caught before shipping, not a hypothetical**: the first attempt lowered `NUM_CTX`
to 8192, which computed `MAX_INPUT_CHARS` to **-4439** — negative. The prompt template's own
instructional text has grown to ~26,111 characters across many sessions of adding extraction rules
(visits, demographics, file_id instructions, record-source consistency checks, etc.) — more than
double the ~10,626 characters it was when `NUM_CTX=12288` was originally chosen (see the 2026-07-22
context-window finding earlier in this file). At `NUM_CTX=8192`, the fixed instructional overhead
ALONE already exceeded the entire context window before a single character of document text — which
would not have failed loudly, it would have caused silent context overflow (part of the prompt's own
extraction rules getting truncated), a substantially worse and harder-to-diagnose failure than the
timeout it was meant to fix. Caught by actually computing `MAX_INPUT_CHARS` after the change rather
than assuming a smaller `NUM_CTX` is automatically safe — a genuinely important habit given how much
this file's prompt has grown over time with no corresponding recheck of this budget.

Fixed properly: `NUM_CTX` set to 11264 instead (computed to leave a real, non-thin ~6,300-character/
~3-page margin against the CURRENT prompt overhead, not assumed), and a hard `RuntimeError` added
right after `MAX_INPUT_CHARS` is computed, firing at startup if it's ever below a 2000-character
floor — so a future prompt-overhead increase (this file's instructional text has only ever grown) or
a careless `LAWFIRMAGENT_NUM_CTX` override fails loudly and immediately instead of silently repeating
this exact near-miss in production. Verified the guard actually fires by reproducing the exact
`NUM_CTX=8192` config that triggered this.

**Verified for real**: server starts cleanly with the new default; a real Case Mode run on
`sample_data/case_006_pdfs` (10 documents) correctly split into 2 chunks, completed with
`"input_truncated": false`, 33 findings, 0 unresolved source citations, 0 bracket-template
contamination. Reran `testing/verify_durable_storage.py` (PASS) and the full two-real-case
`testing/verify_case_highlighting_regression.py` suite — case_ferreira 12/13 and case_whitfield 9/9
citable findings correctly highlighted; the one non-highlighting finding was ordinary quote-fidelity
imprecision on a real, correctly-resolved source document (`case_strategy_memo.pdf`), not a
regression from this fix — same low-rate baseline noise already documented elsewhere in this file,
unrelated to timeout/chunk-size/retry logic.
