# Answer Key — Case 001 (Synthetic)

Ground truth for `case_001_raw_records.md`, written before running any model, so model output can be
scored against it rather than judged "by eye." This mirrors Step 1-2 of `TESTING_PLAN.md`.

## Correct Chronology

| Date | Event | Source |
|---|---|---|
| 12/18/2024 | Pre-op hematology clearance documents heterozygous Factor V Leiden mutation | Record 1 (embedded reference, not its own dated document) |
| 01/06/2025 | Right total knee arthroplasty (TKA), Dr. Okafor, Fairview. Post-op: enoxaparin 40mg SC daily started | Record 1 |
| 01/07/2025 | POD#1: mild calf swelling, attributed to normal post-surgical change, no imaging ordered | Record 2 |
| 01/10/2025 | Discharged home, POD#4. Enoxaparin 40mg SC daily to continue 14 days total | Record 3 |
| 01/15/2025 | PCP visit: patient reports calf tightness + getting winded; attributed to deconditioning; no imaging ordered | Record 4 |
| 01/19/2025 | PT visit: patient reports SOB "for about the last week" (i.e., since ~01/12) and persistent calf ache; PT advises follow-up with physician re: SOB | Record 5 |
| 01/21/2025 | ER: acute SOB + chest pain, hypoxic/tachycardic. CT angiogram: bilateral PE. Admitted ICU, IV heparin started | Record 6 |
| 01/22/2025 | Hematology consult: confirms Factor V Leiden as known risk factor; notes prophylactic (not therapeutic) enoxaparin dose was used; plan to transition to apixaban 10mg BID x7 days then 5mg BID | Record 7 |
| 01/23/2025 | Venous ultrasound confirms (resolved) right lower extremity DVT | Record 8 (embedded reference, not its own dated document) |
| 01/25/2025 | Discharged from St. Adeline. Apixaban 10mg BID x7d then 5mg BID ongoing; enoxaparin discontinued. F/u: hematology 2wk, cardiology 4wk, PCP 1wk | Record 8 |
| 02/01/2025 | PCP follow-up: doing well, no SOB, continuing apixaban | Record 9 |

## Medication Timeline (the conflation trap)

Three different anticoagulants appear across the case — correct extraction must keep them straight
by phase and not merge them:

1. **Enoxaparin 40mg SC once daily** — prophylactic dose, post-op 01/06 → discontinued at 01/25 discharge (~14-19 day course, consistent with the 01/10 note's "14 days total" plan).
2. **Unfractionated heparin, IV drip** — inpatient only, started 01/21 in the ER/ICU, therapeutic by 01/22.
3. **Apixaban 10mg PO BID x7 days, then 5mg PO BID ongoing** — started at hospital discharge 01/25, confirmed continuing 02/01.

A model that says she was "on apixaban after her knee surgery" or "given enoxaparin for her PE" has
conflated the prophylactic and therapeutic drugs — this is the single most likely and most clinically
significant error to watch for, and it's exactly the kind of mistake a citation-grounded verifier
pass should catch (the claim "enoxaparin was given for the PE" does not match any source text).

## Cross-Document Discrepancy (the thing a good chronology should flag)

The 01/15/2025 PCP note frames the shortness of breath as new/mild ("getting winded more easily than
usual") and attributes it to deconditioning, with no imaging ordered. The 01/19/2025 PT note — four
days later — documents the patient describing SOB present "for about the last week," meaning the
symptom was already present (or emerging) at the time of the 01/15 visit but wasn't captured with the
same duration/severity in that note. Neither provider ordered a lower-extremity ultrasound or D-dimer
despite the documented Factor V Leiden mutation being known since 12/18/2024. A strong chronology
output should surface this discrepancy explicitly (differing accounts of symptom onset/duration
across two notes four days apart) rather than silently picking one version. This is the kind of gap
the product doc's "cross-document contradiction/gap detector" (§6) exists to catch.

## Embedded / Non-Headline Dates (easy to miss)

Two dates are mentioned *inside* a note's body text rather than as that note's own document date:

- **12/18/2024** — inside Record 1's text (the pre-op hematology clearance date), not a separate document.
- **01/23/2025** — inside Record 8's text (the venous ultrasound date), not a separate document.

A model doing careless extraction will often either miss these or mistakenly attribute them as the
date of the document they're mentioned in (e.g., reporting the hematology clearance as happening
01/06/2025). Check both explicitly when scoring.

## Vague Field (should not be embellished)

Record 4's chief complaint is just "f/u post-op" with no further detail given in that field. Correct
behavior is to extract it as-is or note it as non-specific — not to invent a more detailed chief
complaint that isn't in the text.

## Scoring Checklist (use this when evaluating a model's output)

- [ ] All 11 chronology events present, in correct date order
- [ ] Both embedded dates (12/18/2024 and 01/23/2025) captured and correctly attributed
- [ ] Three anticoagulants kept distinct — no drug/dose/phase conflation
- [ ] SOB discrepancy between 01/15 and 01/19 notes flagged or at least both versions represented (not silently resolved to one)
- [ ] Vague chief complaint (Record 4) not embellished with invented detail
- [ ] No invented facts not present in any of the 9 records
- [ ] Every claim in the output traceable to a specific Record number
