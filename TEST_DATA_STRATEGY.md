# Getting better test data into the chronology builder's tests

Prompted by a real ~50-file case run through Case Mode that surfaced a cluster of extraction-quality
bugs (Abbreviations/Record Sources empty, Social/PMHx/FHx/PCP never filling in, visit summaries
missed entirely) that none of the existing test data had ever caught — with the explicit ask to stop
and think through why, rather than just patching each symptom.

## 1. What "unit tests" actually means in this repo today

Worth stating plainly, because it's the real starting point: **there is no fast, deterministic unit
test suite.** `find . -iname "test_*.py"` outside vendored/third-party code returns nothing.
`testing/` holds ~25 `verify_*.py` scripts, and almost all of them are Playwright-driven, live-server,
real-Ollama integration tests — they spin up `webapp/app.py` for real, call the actual model, and
check the result. That's not a criticism of the approach (a schema-constrained LLM pipeline's real
failure modes genuinely only show up against a real model — a mocked-out Ollama call would just prove
the mock works), but it means every one of these tests is slow (minutes, not milliseconds), somewhat
non-deterministic (the same fixture can extract slightly differently run to run), and expensive
enough that nobody — including me, session to session — runs the whole suite before every change.
In practice, verification this whole phase has looked like: build/find a fixture, run it through a
live model by hand, eyeball whether the output looks right. That's real verification, but it's
manual and it doesn't accumulate — the next session re-derives it from scratch instead of a suite
that already encodes "here's what must stay true."

That gap — no accumulating, fast, automatic regression net — is arguably the bigger structural
problem here, separate from fixture quality. Both matter; see §4 for what to do about each.

## 2. Why the existing fixtures didn't catch these bugs

`sample_data/case_001` through `case_004` each pair a synthetic `_raw_records.md` with a hand-written
`_answer_key.md` — a real, good pattern (ground truth to assert against, not just eyeballing). But
reading them side by side with what a real 50-file case actually looks like, they share a bias: they
were generated to be easy for a model to extract from correctly, which is the opposite of what a
regression fixture needs. Concretely:
- Demographics (Social Hx, PMHx, FHx, PCP) sat under clean, dedicated headers (`Social History:
  ...`), not as a scattered aside inside an unrelated visit note — real charts almost never state
  "Family History: mother had breast cancer" as its own line; they mention it in passing mid-
  paragraph, in a visit for something unrelated, once, possibly in only one document out of fifty.
  A model correctly reading a clean header proves nothing about whether it'll notice the same fact
  buried in prose.
- Every document read as a distinct, clearly-labeled "record" — none of the original fixtures forced
  the model to tell apart an MD's note from a PT/DPT's note from a radiologist's report through
  context alone, which is exactly the ambiguity that caused visits to collapse into "just labs and
  radiology" in the real case (the safety-net category that should have caught everything else
  didn't have enough distinct provider-type pressure to notice office-visit narratives were being
  systematically skipped).
- All were single-chunk-sized. The real failures (Bates/PDF-source mismatches, empty legends) are
  fundamentally about what happens at MERGE time across many chunks/documents — a fixture too small
  to ever get chunked can't exercise that code path at all, no matter how many times it's run.

None of this was a modeling mistake at fixture-creation time — it's a natural default (synthetic data
generation tends toward clean and legible unless deliberately pushed the other way) — but it created a
blind spot exactly where the real complaints landed.

## 3. `case_006` — a first fixture built specifically to close that gap

Built this session (`sample_data/case_006_raw_records.md` → `scripts/make_test_pdfs.py case_006` →
`sample_data/case_006_pdfs/record_01.pdf`–`record_10.pdf`) as a direct answer to the above, not a
generic "make more data" fixture: 10 documents, varied provider credentials (DO, PT/DPT, MD, an
orthopedic surgeon), full office-visit narratives in the same descriptive style as the real
(anonymized) example shared this session, and demographic facts planted as one-off asides scattered
across different documents — never under a clean header. It already earned its keep: it's what
proved the "visits" category fix (9 visits correctly extracted, provider credentials correctly
differentiated), the demographics-synthesis fix (5 of 7 fields correctly filled from genuinely
scattered mentions), and the crash-resume verification in this same session used it as the real
end-to-end fixture, not a toy.

It does NOT yet have a hand-written answer key like `case_001`–`004` — that's the concrete next step
if this becomes a real assertion-based test rather than an ad hoc verification fixture (see §4).

## 4. Recommendations

**Build a small, deliberately-curated fixture library, not a large generic one.** Five or six
fixtures, each targeting one specific known failure class, beats fifty generic ones — the value is in
what each one is designed to catch, not sample size (this isn't a statistical evaluation, it's a
regression net for known failure modes). Candidates, in priority order:
1. `case_006` (built) — scattered demographics, mixed provider credentials, full visit narratives.
2. A genuinely multi-chunk case (30+ documents, forces real chunking/merge) with a few *intentional*
   near-duplicate records (the same visit from two sources) and a couple of documents with NO Bates
   stamp at all, to keep exercising the page-number-fallback and dedup paths this session touched.
3. A case with real cross-record discrepancies (a medication list that contradicts itself across two
   providers, a fall date that's stated two different ways) — the `discrepancies` field currently has
   the thinnest fixture coverage of any category.
4. A case needing OCR (scanned/faxed-looking pages) paired with a normal text-layer case, so a future
   "should we drop OCR" decision (raised and correctly deferred this session) has real before/after
   data instead of a hunch.
5. A wide-date-range case (DOL as a real range, not a single date) to keep the case-level synthesis
   pass honest.

**Give every new fixture a real answer key, even an informal one.** The `case_001`–`004` pattern
(a paired `_answer_key.md`) is worth keeping and extending to `case_006` and beyond — it's what turns
"I read the output and it looked right" into something a future session (or a real pytest assertion)
can check without re-deriving judgment from scratch.

**Split verification into two real tiers, not one.** This is the bigger structural fix:
- *Fast, deterministic, no-Ollama unit tests* for every part of the pipeline that's actually pure
  logic — `_reconcile_source_files`, `_find_citation_for_quote`/`_resolve_bates`, `_merge_chunk_
  findings`, `_dedupe_with_multi_source`, `_resolve_record_sources`, the crash-resume dispatch logic
  added this session. None of these need a model — they operate on already-produced findings dicts,
  which can just be hand-constructed dicts/tuples in a real `pytest` test. This is exactly the kind
  of test that would have caught, automatically and in milliseconds, two of the real bugs found this
  session: the `"UNKNOWN"`-fake-Bates-marker bug and the file-count-doubling merge bug in the resume
  path — both pure logic bugs, neither needed a model to expose. There is currently zero net catching
  this class of regression; a `pytest.ini` + `testing/unit/` (or similar) with these functions
  imported directly and asserted against hand-built dicts would run in seconds and could reasonably
  gate every change.
- *Slower, answer-key-based extraction-quality tests* (what `case_001`–`006` already are) for the
  genuinely model-dependent behavior test data is actually about. These can't be exact-match
  assertions — the same prompt against the same model won't reproduce byte-identical output run to
  run — but they don't need to be: assert on the STRUCTURAL/PRESENCE facts the answer key states
  (`len(visits) >= 8`, `demographics["family_history"] != "not stated"`, `any("DPT" in v["author"] for
  v in visits)`), the same style of check used to verify results by hand all through this session.
  Formalizing that exact pattern into real test functions (still real-Ollama, still slow, but at
  least runnable unattended and diffable across runs) is a bounded, concrete piece of work — worth
  doing next, once the fixture library above exists to test against.

**Keep new fixtures deliberately messy on purpose.** The one concrete lesson from §2: every new
fixture should be reviewed against a short checklist before being considered "done" — demographics
scattered as asides (not headers), varied provider credentials/record types mixed together, at least
one ambiguous/hard case per fixture (missing Bates, a discrepancy, a near-duplicate). A fixture that
reads too cleanly is a fixture that won't catch the next version of this same class of bug.
