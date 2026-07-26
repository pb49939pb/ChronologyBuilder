# Answer Key — Case 003 (Synthetic)

Ground truth for `case_003_raw_records.md` — a third fact pattern (anticoagulation dosing error).
Unlike Case 001/002, **this one contains a real discrepancy that should be flagged** — it's designed
to test the opposite failure mode: a model tuned to stop inventing false discrepancies shouldn't swing
so far that it stops catching real ones.

## Correct Chronology

| Date | Event | Source |
|---|---|---|
| 05/05/2026 | New AFib diagnosis; warfarin **5mg** daily ordered; INR check planned in 1 week | Record 1 |
| 05/06–05/10/2026 | Home health MAR shows warfarin **10mg** daily administered for 5 days | Record 2 |
| 05/12/2026 | INR critically elevated at 6.8; message left for patient, no documented follow-up contact | Record 3 |
| 05/14/2026 | ER: GI bleed (melena, dizziness), INR 8.4, Hgb 7.1 (baseline ~13); admitted | Record 4 |
| 05/14/2026 | Admission note identifies the 10mg-vs-5mg dosing discrepancy as a likely contributor; reversal agents given, transfused 2 units PRBC | Record 5 |
| 05/15/2026 | Endoscopy: duodenal ulcer with visible vessel, clipped + epinephrine, hemostasis achieved | Record 6 |
| 05/19/2026 | Discharged after 5-day admission; switched to apixaban 5mg BID; medication reconciliation corrected | Record 7 |

## The Real Discrepancy (should be flagged this time)

Record 1 orders warfarin **5mg** daily. Record 2 (the home health MAR) documents **10mg** daily
actually administered for the first 5 days. This is a genuine, factually incompatible conflict
between an order and an administration record — not a paraphrase, not normal progression, an actual
dosing error. Record 5 (the admitting hospitalist) explicitly identifies this discrepancy as a likely
cause of the bleed, which should make it very hard to miss — but confirm the model's own
DISCREPANCIES section states it directly and specifically (the order says 5mg, the MAR says 10mg),
not just a vague mention of "a dosing issue."

## Medication Timeline (distinguish by phase/purpose, don't conflate)

1. **Warfarin 5mg daily** — as *ordered* at the 05/05 cardiology visit.
2. **Warfarin 10mg daily** — as *actually administered* per the home health MAR, 05/06–05/10 (the error).
3. **Vitamin K + 4-factor PCC** — reversal agents given at admission 05/14.
4. **Apixaban 5mg BID** — the new anticoagulant started at discharge 05/19, replacing warfarin entirely.

## Red Flags to Surface

- The dosing error itself (order vs. MAR mismatch) — the central issue of this case.
- A critical INR value (6.8) was called in on 05/12 with only a message left for the patient — no
  documented clinic follow-up or confirmation the patient received/acted on it before the bleed
  occurred two days later. Worth flagging as a missed-notification/follow-up gap, distinct from the
  dosing error itself.
- Record 4 notes the patient "did not follow up herself either" — worth surfacing as relevant
  context (patient-reported) without treating it as resolving or excusing the notification gap.

## Embedded Date Check

No deliberately embedded/non-headline date in this case (unlike Cases 001/002) — this case's main
test is the real-discrepancy detection and dosing-error tracking, not date extraction.

## Scoring Checklist

- [ ] All 7 chronology events present, in correct date order
- [ ] The 5mg-ordered vs. 10mg-administered conflict correctly flagged as a genuine DISCREPANCY (not omitted, not vague)
- [ ] Four medication phases (ordered warfarin, administered warfarin, reversal agents, discharge apixaban) kept distinct
- [ ] Missed INR follow-up/notification gap flagged as a potential issue, separate from the dosing error
- [ ] No invented facts not present in any of the 7 records
- [ ] Every claim traceable to a specific Record number
