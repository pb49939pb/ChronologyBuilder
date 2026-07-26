# Answer Key — Case 004 (Synthetic, 31 documents / 31 pages)

Ground truth for `case_004_raw_records.md`. Unlike case_001-003 (7-13 documents), this case is
deliberately large — 31 separate documents across an 22-day hospital stay — to test whether the
pipeline can track a **trend across many repetitive documents**, not just extract a fact from one.
At ~21K characters this run comfortably fits this model's context budget (~32K chars); if the
budget is ever lowered, or a real case's documents are denser than these synthetic ones, this is
the case to rerun to check truncation behavior.

## The Core Pattern (this is the real test)

Creatinine trends upward in **every single daily progress note** from 0.9 (admission baseline) to
4.4 (18 days later), documented as an isolated lab value in each note without commentary connecting
one day's value to the next. No single document states "this has been rising for two weeks" — that
synthesis has to happen ACROSS documents. Nephrology isn't consulted until day 18, and a renal
ultrasound (day 16) is the first point anyone investigates the trend at all.

**A strong review should flag this as a potential issue**: acute kidney injury was documented daily
for over two weeks without triggering nephrology consultation, additional workup, or a change in
management until very late in the admission — this is the central potential-issue finding this case
is built around, and it's much harder to catch than case_001-003's single-document red flags because
no individual document says "this is a problem," only the accumulated trend across ~20 documents does.

## Correct Chronology (abbreviated — full version has 31 dated entries, one per document)

| Date | Event |
|---|---|
| 06/10/2026 | ED presentation: sepsis, hypotension, confusion. Baseline creatinine 0.9 (per prior outside records) |
| 06/10/2026 | ICU admission H&P: sepsis, no AKI at baseline |
| 06/11/2026 – 06/27/2026 | 18 daily ICU progress notes, creatinine rising each day: 1.1 → 1.2 → 1.3 → 1.5 → 1.7 → 1.9 → 2.1 → 2.3 → 2.5 → 2.8 → 3.0 → 3.3 → 3.5 → 3.7 → 3.9 → 4.0 → 4.2 → 4.4 |
| 06/22/2026 | ID consult: antibiotic de-escalation (unrelated to the AKI trend — a distractor, not part of the core pattern) |
| 06/26/2026 | Renal ultrasound: no obstruction, no structural cause found |
| 06/28/2026 | Nephrology consult, day 18: severe AKI, recommends dialysis |
| 06/28/2026 | Hemodialysis initiated |
| 06/29/2026 – 07/02/2026 | Post-dialysis stabilization, case management, discharge to a dialysis-capable rehab facility |

## Distractor Elements (should NOT be over-weighted)

- The ID consult (day 12) is about antibiotic de-escalation for the *resolving sepsis*, unrelated to
  the kidney injury — a good review shouldn't conflate these two threads.
- Several nursing notes mention nonspecific fatigue/withdrawal, plausibly attributable to prolonged
  hospitalization — these are worth noting as context but shouldn't be treated as definitive AKI
  symptoms on their own merit; the LAB TREND is the real signal.
- The family's day-27 comment ("she doesn't seem to be getting better") is a real, useful potential-
  issue signal (documented concern predating the eventual nephrology consult by a day) — a strong
  review should catch this as corroborating evidence for a delayed-recognition finding.

## Scoring Checklist

- [ ] Chronology captures the overall arc (admission → progressive AKI → dialysis → discharge) even if not literally all 31 dates are itemized
- [ ] **The core finding**: rising creatinine across many days without nephrology consultation/workup until day 18 is flagged as a potential issue — this is the single most important thing this test case checks for
- [ ] ID consult (day 12) not confused with or conflated into the AKI/nephrology thread
- [ ] No invented facts; every claim traceable to a specific document
- [ ] Check whether `input_truncated` was reported in the stats — if so, note which documents likely got cut off and whether the core finding still came through despite truncation
