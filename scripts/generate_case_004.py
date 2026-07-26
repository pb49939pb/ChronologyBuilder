#!/usr/bin/env python3
"""
Generates sample_data/case_004_raw_records.md — a longer, ~30 document synthetic case (prolonged
ICU stay, progressive acute kidney injury missed across many repetitive daily notes until it
requires dialysis) designed to be large enough (30-40 rendered pages) to actually exceed the
model's context budget, unlike the shorter case_001-003 test cases. Entirely fictional.

Usage: python3 generate_case_004.py
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "sample_data" / "case_004_raw_records.md"

HEADER = """# SYNTHETIC TEST DATA — NOT A REAL PATIENT

This file is entirely fictional, generated for testing the LawFirmAgent pipeline against a much
longer document set than case_001-003 — long enough (30-40 rendered pages) to exceed this model's
context budget, which is itself the point of this test case: real cases often run far longer than
what fits in a single pass, and this is meant to exercise (and honestly document) what happens when
that budget is exceeded, not just cases that comfortably fit.

Fact pattern: a patient admitted with sepsis develops progressive acute kidney injury over an 18-day
ICU/stepdown stay. The rising creatinine trend is documented in every daily note, but nephrology
isn't consulted until day 18, by which point the patient requires dialysis — a realistic "the signal
was there in the routine documentation the whole time, but spread across many similar-looking daily
notes" pattern, and a genuinely harder test of whether an extraction pipeline can track a trend
across many repetitive documents rather than a single obvious fact in one document.

---

**Patient:** Margaret Okwuosa
**MRN:** SYN-04471 (synthetic)
**DOB:** 02/17/1953

---

"""

# (day, creatinine, notable narrative addition beyond the templated vitals/status)
DAILY_NOTES = [
    (1, 1.1, "Foley catheter removed. Ambulating with assistance. Continues on IV piperacillin-tazobactam for sepsis source control."),
    (2, 1.2, "Oral intake improving. Antibiotics continued. Physical therapy evaluation completed, recommends continued inpatient therapy."),
    (3, 1.3, "Low-grade fever overnight, 100.6F, resolved by morning. Antibiotics continued unchanged."),
    (4, 1.5, "Mild lower extremity edema noted, attributed to IV fluid resuscitation during initial sepsis management."),
    (5, 1.7, "Urine output adequate per nursing flowsheet. Diet advanced to regular. Case management initiated discharge planning discussion."),
    (6, 1.9, "Patient reports mild fatigue, otherwise stable. Vital signs within normal limits. Continue current management."),
    (7, 2.1, "Repeat blood cultures negative. Antibiotic course nearing completion. Plan to transition to oral antibiotics if afebrile."),
    (8, 2.3, "Transitioned to oral levofloxacin. Patient tolerating diet well. Ambulating in hallway with physical therapy."),
    (9, 2.5, "Family meeting held to discuss anticipated discharge to rehabilitation facility later this week."),
    (10, 2.8, "Patient noted to be more fatigued than prior days per nursing. Oral intake slightly decreased."),
    (11, 3.0, "Mild confusion noted overnight per nursing, resolved by morning rounds. Attributed to poor sleep."),
    (12, 3.3, "ID consulted today for antibiotic de-escalation planning given clinical improvement — see separate consult note."),
    (13, 3.5, "Continues on de-escalated antibiotic regimen per ID recommendations. Ambulating independently in room."),
    (14, 3.7, "Patient reports mild nausea, no vomiting. Diet tolerated with small modifications. Otherwise unremarkable overnight."),
    (15, 3.9, "Family updated on continued slow progress. Oral intake adequate. No new complaints overnight per nursing."),
    (16, 4.0, "Mild lower extremity swelling again noted, similar to earlier in admission. Continue monitoring."),
    (17, 4.2, "Patient more withdrawn today per nursing observation, attributed to prolonged hospitalization and fatigue."),
    (18, 4.4, "Nephrology consulted today given progressive rise in creatinine over the admission — see separate consult note."),
]


class RecordCounter:
    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return self.n


def daily_note_text(rec_num: int, day: int, creatinine: float, narrative: str) -> str:
    date = f"06/{(10 + day):02d}/2026"
    bun = round(creatinine * 14 + 8, 0)
    return f"""### Record {rec_num} — Fairview General Hospital — ICU Progress Note, Day {day}

**Date of Service:** {date}
**Provider:** Dr. T. Anand, Hospitalist

Subjective: Patient resting comfortably overnight per nursing report. {narrative}

Objective: Temp 98.9F, HR 82, BP 128/76, RR 16, SpO2 96% on room air. Lungs clear. Abdomen soft,
non-tender. Labs: Creatinine {creatinine}, BUN {bun:.0f}, WBC within normal limits, potassium 4.2.

Assessment: Sepsis, improving. Acute kidney injury, stable per prior trend.

Plan: Continue current management. Daily labs. Nutrition and mobility per physical therapy."""


def nursing_note_text(rec_num: int, date: str, shift: str, content: str) -> str:
    return f"""### Record {rec_num} — Fairview General Hospital — Nursing Shift Note ({shift})

**Date/Time:** {date}
**Nurse:** R. Alvarez, RN

{content}"""


def build():
    c = RecordCounter()
    parts = [HEADER.strip()]

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — Emergency Department Note

**Date of Service:** 06/10/2026
**Provider:** Dr. L. Fenwick, Emergency Medicine

Chief complaint: Fever, confusion, low blood pressure.

HPI: 73-year-old female brought in by family for 2 days of fever, confusion, and decreased oral
intake. Family reports she has seemed "not herself" and increasingly drowsy today.

Vitals: Temp 102.4F, HR 118, BP 84/52, RR 24, SpO2 91% on room air.

Labs: WBC 18.4, Lactate 3.8, Creatinine 0.9 (baseline, per prior outside records), BUN 22.

Assessment: Sepsis, likely urinary source given urinalysis findings, with associated hypotension.

Plan: IV fluid resuscitation, blood and urine cultures drawn, empiric IV piperacillin-tazobactam
started, admit to ICU for close monitoring.""")

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — ICU Admission History & Physical

**Date of Service:** 06/10/2026
**Provider:** Dr. T. Anand, Hospitalist

History: 73-year-old female with history of hypertension and osteoarthritis, admitted from the ED
with sepsis of likely urinary origin, presenting with fever, altered mental status, and hypotension.

Baseline renal function: Creatinine 0.9 on outside records from a primary care visit 3 months prior,
described there as "stable, at patient's baseline."

Assessment: Sepsis with hypotension, responding to fluid resuscitation. Mental status improving.
No acute kidney injury at this time; renal function within patient's known baseline.

Plan: Continue IV antibiotics pending culture results, IV fluids, strict intake/output monitoring,
daily basic metabolic panel to trend renal function during recovery.""")

    parts.append(nursing_note_text(
        c.next(), "06/11/2026, 07:00", "Night",
        "Patient slept intermittently. Vital signs stable per flowsheet. IV antibiotics administered "
        "on schedule. Foley catheter output adequate overnight. No acute events to report.",
    ))

    for day, creatinine, narrative in DAILY_NOTES[:5]:
        parts.append(daily_note_text(c.next(), day, creatinine, narrative))

    parts.append(nursing_note_text(
        c.next(), "06/15/2026, 19:00", "Evening",
        "Patient ambulated in hallway twice this shift with physical therapy assistance. Tolerated "
        "dinner tray well. Family visited. No new complaints voiced to nursing staff this shift.",
    ))

    for day, creatinine, narrative in DAILY_NOTES[5:11]:
        parts.append(daily_note_text(c.next(), day, creatinine, narrative))

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — Infectious Disease Consult Note

**Date of Service:** 06/22/2026
**Provider:** Dr. S. Whitcombe, Infectious Disease

Reason for consult: Antibiotic de-escalation planning given clinical improvement in sepsis.

Assessment: Sepsis of urinary origin, clinically improved. Recommend transition to targeted oral
therapy per culture sensitivities, continuing for a total 14-day course from initial positive
culture.

Plan: De-escalate to oral nitrofurantoin. ID to follow as needed; no further routine follow-up
planned unless clinical status changes.""")

    parts.append(nursing_note_text(
        c.next(), "06/23/2026, 07:00", "Night",
        "Patient reports feeling 'more tired than usual' overnight but denies pain or shortness of "
        "breath. Vital signs stable. Ambulated to bathroom with standby assistance x2 overnight.",
    ))

    for day, creatinine, narrative in DAILY_NOTES[11:15]:
        parts.append(daily_note_text(c.next(), day, creatinine, narrative))

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — Radiology Report

**Date of Service:** 06/26/2026
**Study:** Renal ultrasound
**Interpreting Provider:** Dr. K. Nishimura, Radiology

Clinical indication: Rising creatinine, evaluate for obstruction or structural abnormality.

Findings: Kidneys are normal in size bilaterally, no hydronephrosis, no obstructing stones
identified. No structural cause for renal impairment identified.

Impression: No obstructive process. Findings do not explain the degree of renal function decline;
clinical correlation recommended.""")

    for day, creatinine, narrative in DAILY_NOTES[15:17]:
        parts.append(daily_note_text(c.next(), day, creatinine, narrative))

    parts.append(nursing_note_text(
        c.next(), "06/27/2026, 19:00", "Evening",
        "Patient appears more fatigued than baseline for this admission per this nurse's assessment, "
        "spending most of shift resting in bed rather than ambulating as in recent days. Family at "
        "bedside, voiced concern that 'she doesn't seem to be getting better.' Concern relayed to "
        "covering physician per usual communication process.",
    ))

    day, creatinine, narrative = DAILY_NOTES[17]
    parts.append(daily_note_text(c.next(), day, creatinine, narrative))

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — Nephrology Consult Note

**Date of Service:** 06/28/2026
**Provider:** Dr. R. Castellanos, Nephrology

Reason for consult: Progressive rise in creatinine over the course of hospitalization, from a
baseline of 0.9 on admission to 4.4 today, 18 days into this admission.

Review of daily labs throughout this admission shows a steady, essentially uninterrupted upward
trend in creatinine from the day of admission onward, without evidence that this trend prompted
nephrology consultation, a renal ultrasound, or a change in management until a renal ultrasound was
obtained on day 16 and this consult today.

Assessment: Severe acute kidney injury, likely a combination of sepsis-related acute tubular injury
and possible contribution from volume status changes over the admission. Given the current degree of
renal impairment and associated symptoms, initiation of renal replacement therapy is recommended.

Plan: Begin hemodialysis today. Nephrology to follow daily during remainder of admission.""")

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — Hemodialysis Initiation Note

**Date of Service:** 06/28/2026
**Provider:** Dr. R. Castellanos, Nephrology

Temporary dialysis catheter placed without complication. First hemodialysis session completed today,
tolerated with stable blood pressure throughout. Plan for continued dialysis sessions per nephrology
protocol, with reassessment of native kidney function recovery over the coming weeks.""")

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — ICU Progress Note, Day 19

**Date of Service:** 06/29/2026
**Provider:** Dr. T. Anand, Hospitalist

Patient post first hemodialysis session, hemodynamically stable. Mental status clear. Family updated
on new need for dialysis and plan for ongoing nephrology follow-up after discharge.

Assessment: Sepsis, resolved. Acute kidney injury requiring hemodialysis.

Plan: Continue dialysis per nephrology. Begin discharge planning to a facility capable of
outpatient dialysis coordination.""")

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — Case Management Note

**Date of Service:** 06/30/2026
**Provider:** J. Reyes, Case Manager

Discharge planning updated given new need for ongoing outpatient hemodialysis, which was not
anticipated in the original discharge plan discussed with family on hospital day 9. Working to
identify a rehabilitation facility with dialysis capability; this has extended anticipated discharge
timeline by approximately one week compared to the original plan.""")

    parts.append(f"""### Record {c.next()} — Fairview General Hospital — Discharge Summary

**Date of Service:** 07/02/2026
**Discharging Provider:** Dr. T. Anand, Hospitalist

Discharge diagnosis: Sepsis of urinary origin, resolved. Acute kidney injury requiring hemodialysis,
initiated hospital day 18.

Hospital course: 22-day admission for sepsis with associated acute kidney injury. Renal function
declined progressively throughout the admission, with a renal ultrasound obtained on hospital day 16
showing no obstructive cause, followed by nephrology consultation and initiation of hemodialysis on
hospital day 18. Patient's condition stabilized following dialysis initiation.

Discharge plan: Transfer to Willowbrook Rehabilitation Center, which has onsite dialysis capability.
Continue hemodialysis three times weekly. Nephrology follow-up in 1 week. Primary care follow-up in
2 weeks.""")

    OUT.write_text("\n\n---\n\n".join(parts) + "\n")
    print(f"wrote {OUT} ({c.n} records)")


if __name__ == "__main__":
    build()
