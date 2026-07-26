# Research Notes — Nurse Paralegal Chronology Practice & HIPAA/Security Posture

Background research done between build tasks, per the user's request to use idle time productively.
Two threads: (1) how nurse paralegals/legal nurse consultants actually build chronologies in
professional practice, so the tool's output shape matches real work product conventions rather than
something invented from scratch, and (2) what "as secure as possible, HIPAA-compliant" concretely
requires in 2026, to sanity-check `PRODUCT_DEFINITION.md` §7 against current guidance rather than
assumptions from when it was first written.

## Part 1: How Nurse Paralegals / Legal Nurse Consultants Actually Build Chronologies

### The role, more precisely

"Nurse paralegal" is an informal label for what the profession's own association calls a **Legal
Nurse Consultant (LNC)**. The American Association of Legal Nurse Consultants (AALNC) publishes a
formal Scope and Standards of Practice, and offers the **LNCC (Legal Nurse Consultant Certified)**
credential — accredited by the Accreditation Board for Specialty Nursing Certification and recognized
by the ANCC Magnet Recognition Program. Eligibility requires 5 years of RN experience plus 2,000
hours of LNC work within the prior 5 years; certification is valid for 5 years. This is a real,
credentialed specialty with its own professional standards body — not an informal role attorneys made
up, which matters for how much weight a well-built chronology can carry in litigation.

### Standard chronology format

Across multiple LNC practice sources, the format is remarkably consistent: **Date, Description,
Page/Source citation, Comments**, arranged in strict chronological order — even though the
underlying medical records are almost always received in *reverse*-chronological order (most recent
first), which is itself one of the first things an LNC has to invert. Chronologies come in two
flavors depending on purpose: a **summary chronology** (condensed, for general case understanding)
or a **word-for-word transcription** of selected entries, used when a specific treater is scheduled
for deposition and their exact language matters.

**The one concrete gap this surfaces for our build:** every source treats **page-level citation as
non-negotiable** — "cross-reference every entry with the specific page number in the medical
records" is described as vital, not optional. Our current schema only tracks `source_file`, not a
page number, even though our own pipeline (the browser-side `findQuoteInDoc` search) already knows
which page a quote was found on internally — it's just not surfaced to the user or the export. This
is a concrete, low-effort improvement worth making: add `page` to the finding schema and the export
format, both because it matches how the profession actually works and because it's free — we already
compute it.

### FRE 1006 — why the citation discipline isn't just a nicety

Federal Rule of Evidence 1006 permits summaries to prove the content of voluminous documents that
can't conveniently be examined in court — which is exactly the role a medical chronology plays. Three
conditions apply, and all three point at design choices we've already made for other reasons:

1. **The underlying documents themselves must be admissible.** Our approach doesn't touch this (a
   legal question for the attorney), but it does mean the chronology is only as good as its
   traceability *back to* those documents — reinforcing why every finding needing a real, verbatim
   quote isn't just an anti-hallucination measure, it's aligned with the actual evidentiary
   requirement.
2. **The proponent must show the summary accurately reflects the documents.** This is precisely what
   the human-review/approve-reject workflow exists to satisfy — a summary nobody has verified against
   source doesn't meet this bar, regardless of how it was produced.
3. **Original documents must be made available to opposing counsel for examination.** Not something
   software solves, but worth knowing as a hard requirement independent of anything technical.

One more detail worth knowing: a 2024 amendment to Rule 1006 corrected a mistaken line of case law
where some courts had treated a Rule 1006 summary as "not evidence" requiring a limiting instruction
— it *is* evidence, on equal footing with anything else admitted. That raises the stakes on accuracy
rather than lowering them, since a flawed AI-assisted chronology admitted as substantive evidence is
a bigger problem than one that's merely a demonstrative aid.

### What this means for the product, concretely

- **Add page numbers to the finding schema and export.** `findQuoteInDoc` already determines the page
  a quote lives on — surfacing `match.pageNum` in the structured findings (not just internally for
  rendering) would bring the tool's output in line with how every professional chronology in this
  field is actually cited. Not yet implemented; flagged here as the most concrete, low-effort next
  step from this research.
- **The traceability/verbatim-quote design wasn't arbitrary** — it happens to match both professional
  LNC practice and FRE 1006's accuracy requirement independently. Worth stating explicitly in
  `PRODUCT_DEFINITION.md` as validation, not just an internal design choice.
- **Consider supporting a "verbatim transcription" mode** for specific documents/entries, matching
  the profession's real distinction between a condensed summary chronology and a word-for-word
  transcription used for deposition prep — not built, but a plausible future detail-level option
  beyond the current Brief/Standard/Detailed slider (which controls scope, not transcription fidelity).

## Part 2: HIPAA / Security Posture — 2026 Update

### The Security Rule is changing, and the direction matters even before it's final

HHS published a Notice of Proposed Rulemaking (December 2024) proposing the first major HIPAA
Security Rule overhaul since 2013. As of this research, the rule isn't finalized (targeted for
around mid-2026 per OCR's regulatory agenda, with a compliance window to follow) — but the direction
is clear and worth building toward now rather than waiting:

**The proposal eliminates the "addressable vs. required" distinction entirely.** Today, some
safeguards are technically "addressable" (implement, or document why not and use an equivalent
alternative). The proposed rule makes the following **mandatory, full stop, for every covered entity
and business associate**:

- **Multi-factor authentication** on every system touching ePHI — not just the "important" ones.
- **Encryption**: AES-256 (or equivalent) at rest, TLS 1.2+ in transit, with no addressable escape
  hatch.
- **Vulnerability scanning**: automated, at least every 6 months, both internal and external.
- **Penetration testing**: at least annually, or more often if the org's own risk analysis calls for
  it.
- **Incident response planning** as a standing requirement, not a reactive afterthought.
- **Risk analysis**: annually, and after any major environmental change — regulators are explicitly
  signaling a move away from ad-hoc, reactive risk assessment toward continuous, proactive practice.

None of this is finalized law yet, but a firm building a system now should treat the *direction* of
travel as the actual bar, not the current minimum — building to "addressable, we chose not to" is
building toward a standard about to be retired.

### What this changes in `PRODUCT_DEFINITION.md` §7

The existing compliance checklist (MFA, AES-256, TLS 1.2+, audit logging, retention policy, incident
response, no internet egress) already anticipated most of this correctly. Two additions worth making
there explicitly once the firm-approval phase begins:

- A **recurring vulnerability scan cadence** (≥ every 6 months) and an **annual penetration test**
  aren't currently listed as ongoing operational requirements — they should be, given where the rule
  is heading.
- **Risk analysis as a recurring, scheduled activity** (annual minimum, plus after any environment
  change — e.g., swapping models, changing hardware, adding a new integration) rather than a one-time
  gate at Phase 0.

### Air-gapped / local-LLM-specific security practices

Separate from HIPAA's general requirements, there's a growing body of practice specific to running
LLMs entirely offline that's directly relevant to this project's actual architecture:

- **A genuine air gap** means no WAN connection, no external DNS resolution, and no outbound telemetry
  of any kind — including for licensing/update checks. Updates, if needed, come in via write-once
  media or an equally deliberate one-way transfer, not routine internet access. This is a stricter
  bar than "firewalled" — worth knowing as the target state even if the current prototype (firewalled,
  not literally air-gapped) is a reasonable interim step.
- **A practical local-LLM security checklist** commonly cited: disable telemetry (we did this —
  `OLLAMA_NO_CLOUD=1`, found and fixed the same day it mattered), verify model file checksums before
  use, bind the inference port to localhost only (already true — confirmed empirically earlier this
  project), keep disk encryption enabled, keep the inference tool itself (Ollama, in our case)
  updated to patch known vulnerabilities, and — specific to anything that touches local LLMs more
  broadly — audit any *other* software with system-prompt-level access to the model for a path that
  could exfiltrate data (e.g., a browser extension or productivity-tool integration with model
  access). That last one isn't a concern for this specific single-purpose app, but is worth
  remembering if this project ever grows additional integrations.
- **Model file integrity**: there's a theoretical risk of a malicious GGUF (the local model file
  format) exploiting a parser vulnerability in llama.cpp — no widespread confirmed incidents as of
  this research, but the mitigating practice is simple: pull models from a trusted source (Hugging
  Face / Ollama's own library, both of which publish verifiable checksums) rather than an arbitrary
  download link, which is already how this project has sourced every model.
- **Expect a capability lag, and plan around it, not against it.** Air-gapped/offline AI deployments
  typically lag the best publicly-available cloud models by something like 6-12 months in raw
  capability, precisely because of the deliberate friction in getting new models validated and
  transferred into an isolated environment. This isn't a flaw to route around — it's the actual,
  reasonable cost of the "nothing leaves this machine" guarantee that's the whole point of this
  project, and it reinforces why the human-verification workflow can't be treated as a temporary
  scaffold to remove once models improve — the security architecture itself guarantees the on-prem
  model will usually be a step behind the frontier.

## Summary — What to Actually Do With This

Two concrete, currently-unimplemented action items came out of this research, both flagged rather
than built yet (this was research time, not a build task):

1. Add page numbers to the finding schema/export — cheap, already computed internally, matches how
   the profession actually cites sources and what FRE 1006 practice expects.
2. Update `PRODUCT_DEFINITION.md` §7's compliance checklist with an explicit recurring
   vulnerability-scan/penetration-test/risk-analysis cadence, anticipating where the 2026 HIPAA
   Security Rule update is heading rather than only meeting today's baseline.

Everything else in this document is context that validates decisions already made (citation
discipline, `OLLAMA_NO_CLOUD`, localhost-only binding, sourcing models from trusted registries) rather
than calling for new work.

## Part 3: PDF Extraction/Display Standards, and Chronology Practice Follow-Up (2026-07-22)

### PDF text extraction — validates the column-reconstruction approach already built

Researched current best practice for extracting readable text from PDFs (prompted by the real
medication-list-truncation bug found and fixed the same day — see `TEST_RESULTS.md`). The
established academic/industry approach is a three-stage pipeline: **detect contiguous text blocks
via spatial layout, classify them, then stitch them together in correct reading order** — which is
exactly what `_extract_page_text()` in `webapp/app.py` does (detect a column gutter, then read each
column fully before moving to the next), arrived at independently by directly diagnosing a real
failure rather than following a known method. Good confirmation the approach is principled, not a
one-off hack.

**One avenue checked and deliberately not pursued further**: well-formed, accessibility-authored
PDFs (PDF/UA "Tagged PDF") embed an explicit structure tree defining true logical reading order,
which would be more reliable than geometric inference where present. `pdfplumber` does expose this
(`page.structure_tree`) — checked it directly against both a real document (the "Visit Summary"
export) and our synthetic test PDFs: both come back with an empty structure tree. Auto-generated
EHR exports and reportlab-generated test PDFs simply don't include this, in practice — confirming
the geometric column-detection fallback is the right primary approach for this document population,
not a stopgap to replace once "done properly."

### PDF display — confirms the citation/highlighting design direction

Legal document review tools in 2026 converge on the same pattern already built here: clickable
citations that jump to and highlight the exact supporting passage in the source document, rather
than a separate summary disconnected from the underlying record. Nothing here suggested a UI
direction the app doesn't already have — useful as confirmation, not a new action item.

### OCR — a concrete, quantified expectation for handwriting specifically

Found real, sobering numbers worth setting expectations by: traditional/non-AI OCR (which is what
`easyocr` is — a CNN-based text recognizer, not a vision-language model) gets roughly **50-70%
accuracy on genuine handwriting**, averaging around **64%** across tools, versus **82-95%** for
purpose-built AI/vision-language-model handwriting OCR. This means: expect `easyocr` to do fine on
scanned/faxed *typed* documents (confirmed already — see the earlier synthetic scanned-page test),
but expect it to genuinely struggle on real handwritten physician notes specifically, not as a bug
to fix via better settings but as a real capability ceiling of this class of OCR engine. This
directly informed the OCR test plan below — test handwriting separately from typed-but-scanned
documents, and don't expect the same fix to help both.

### Chronology practice — one concrete gap found, one prompt change made

Additional LNC-practice research surfaced a distinction the existing prompt doesn't currently ask
for: professional chronologies explicitly separate **pre-existing conditions/history predating the
injury or incident** from **new findings caused by or following it** — described as one of the
concrete things a chronology is specifically for (surfacing "pre-existing conditions or prior
injuries that may impact the claim" as their own reviewable category, since a defense will often
argue an outcome traces to a pre-existing condition rather than a new complication). The existing
prompt/schema doesn't ask the model to make this distinction explicit anywhere. Added an instruction
to `prompts/chronology_prompt_structured.txt` (see the "PRE-EXISTING VS. NEW" section) asking the
model to explicitly flag, in the `text` field of any timeline/diagnosis entry describing a condition
also mentioned as pre-existing/chronic elsewhere in the record, that it predates the events in
question — a low-cost prompt addition addressing a real, professionally-recognized category this
tool wasn't previously asked to distinguish.
