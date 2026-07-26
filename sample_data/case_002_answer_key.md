# Answer Key — Case 002 (Synthetic)

Ground truth for `case_002_raw_records.md` — a different fact pattern from Case 001 (delayed
diagnosis of perforated appendicitis) for test variety.

## Correct Chronology

| Date | Event | Source |
|---|---|---|
| 03/02/2026 | Urgent care visit: RLQ tenderness documented on exam, diagnosed as gastroenteritis, ondansetron prescribed, no imaging/labs ordered | Record 1 |
| 03/03/2026, 21:40 | Nurse telephone triage: spouse reports worsening pain, patient "can't stand up straight"; advised to continue conservative management | Record 2 |
| 03/04/2026 | ER visit: perforated appendicitis with peritonitis diagnosed via CT, WBC 18.2, emergent surgical consult | Record 3 |
| 03/04/2026 | Emergent appendectomy + peritoneal washout; findings consistent with several days of untreated appendicitis | Record 4 |
| 03/06/2026 | ICU progress note, POD#2: evolving sepsis, vancomycin added to piperacillin-tazobactam | Record 5 |
| 03/09/2026 | Surgical drain removed | Record 6 (embedded reference, not its own dated document) |
| 03/11/2026 | Discharged after 7-day admission; transitioned to oral amoxicillin-clavulanate x5 days | Record 6 |
| 03/20/2026 | Internal peer review/quality note on the initial urgent care visit and triage call | Record 7 |

## Medication Timeline (conflation trap)

Four different drugs appear, serving different purposes at different phases:
1. **Ondansetron 4mg ODT** — anti-nausea, prescribed at the 03/02 urgent care visit.
2. **Piperacillin-tazobactam IV** — broad-spectrum antibiotic, started at ER presentation 03/04.
3. **Vancomycin IV** — added 03/06 in the ICU for broader coverage given persistent leukocytosis.
4. **Amoxicillin-clavulanate (oral)** — discharge antibiotic, started 03/11 for 5 additional days.

A model that says the patient was "given amoxicillin for his nausea" or conflates any of these
has made a real, clinically significant error — watch for this specifically.

## The Discrepancy Trap (this one should NOT be flagged as a discrepancy)

Record 1 (03/02) documents only "mild tenderness," while Record 2 (03/03, one day later) reports the
patient "can't stand up straight." **This is not a contradiction** — it's normal, expected symptom
progression over 24 hours for worsening appendicitis, not two conflicting accounts of the same
moment in time. A good model should recognize these as consistent with clinical worsening (correctly
NOT flagging a "discrepancy"), while still flagging the more important point under **potential
issues**: reported worsening symptoms were managed with continued conservative advice rather than a
same-day in-person re-evaluation, which is the actual red flag here — this is the same "don't confuse
progression/worsening with contradiction" test as Case 001's SOB pair, applied in the opposite
direction (testing under-flagging this time, not over-flagging).

## Red Flags a Strong Review Should Surface

- No imaging or labs ordered at the initial urgent care visit despite documented RLQ tenderness.
- Telephone triage handling reported worsening symptoms ("can't stand up straight") with continued
  conservative advice rather than recommending immediate in-person evaluation.
- Record 7 (the facility's own peer review note) independently corroborates both of the above points
  — a strong answer should notice that the peer review note is itself evidence supporting the
  potential-issue findings, not just another chronology entry.

## Embedded / Non-Headline Date (easy to miss)

**03/09/2026** — the drain-removal date — appears inside Record 6's body text, not as its own
document's date. Same failure mode as Case 001: check whether the model catches this or silently
drops it.

## Scoring Checklist

- [ ] All 8 chronology events present, in correct date order
- [ ] Embedded date (03/09/2026) captured and correctly attributed to Record 6
- [ ] Four medications kept distinct — no drug/purpose/phase conflation
- [ ] 03/02 vs 03/03 symptom progression NOT flagged as a discrepancy (it's real worsening, not a contradiction)
- [ ] Delayed imaging/escalation flagged as a potential issue (both at the urgent care visit and the triage call)
- [ ] Record 7 (peer review note) recognized as corroborating evidence, not just logged as a bare entry
- [ ] No invented facts not present in any of the 7 records
- [ ] Every claim traceable to a specific Record number
