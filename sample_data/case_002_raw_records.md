# SYNTHETIC TEST DATA — NOT A REAL PATIENT

This file is entirely fictional, written for testing the LawFirmAgent extraction pipeline. No real
patient, provider, or facility is represented. A different fact pattern from Case 001 (delayed
diagnosis of appendicitis rather than a post-op PE) to give the test suite more variety.

---

**Patient:** Daniel R. Ferreira
**MRN:** SYN-00892 (synthetic)
**DOB:** 09/14/1994

---

### Record 1 — Crestline Urgent Care — Visit Note

**Date of Service:** 03/02/2026

Chief complaint: Abdominal pain, nausea.

HPI: 31-year-old male with 1 day of periumbilical abdominal pain, now migrating to right lower
quadrant, associated with nausea and one episode of vomiting. Denies fever at home. Last bowel
movement yesterday, normal.

Exam: Abdomen soft, mild tenderness right lower quadrant, no rebound or guarding noted. Temp 99.1F.

Assessment: Likely viral gastroenteritis.

Plan: Ondansetron 4mg ODT for nausea. Clear liquids, advance diet as tolerated. Return if worsening
pain, fever, or vomiting.

---

### Record 2 — Crestline Urgent Care — Nurse Telephone Triage Note

**Date/Time:** 03/03/2026, 21:40

Patient's spouse called reporting patient's abdominal pain "has gotten worse today" and patient now
"can't stand up straight." Advised per protocol to continue clear liquids and the anti-nausea
medication prescribed yesterday, and to go to the emergency department if pain becomes severe or he
develops a fever. Spouse verbalized understanding.

---

### Record 3 — Overlake Regional Medical Center — Emergency Department Note

**Date of Service:** 03/04/2026

Chief complaint: Severe abdominal pain.

HPI: 31-year-old male, seen at urgent care 2 days ago for abdominal pain and diagnosed with
gastroenteritis. Presents today with severe right lower quadrant pain, now with guarding, fever of
102.3F, and rigid abdomen. Spouse reports patient described pain as "unbearable" beginning last
night and worsening progressively since the urgent care visit.

Exam: Rigid abdomen, marked rebound tenderness RLQ, positive Rovsing's sign. Ill-appearing.

Labs: WBC 18.2 (elevated). CT abdomen/pelvis: perforated appendix with periappendiceal abscess and
free fluid, concerning for early peritonitis.

Assessment: Perforated appendicitis with peritonitis.

Plan: Emergent surgical consult, IV antibiotics (piperacillin-tazobactam) started, to OR.

---

### Record 4 — Overlake Regional Medical Center — Operative Report

**Date of Service:** 03/04/2026
**Surgeon:** Dr. M. Okonkwo-Reyes

Procedure: Emergent laparoscopic-converted-to-open appendectomy with peritoneal washout.

Findings: Perforated appendix with surrounding abscess and purulent free fluid throughout the
abdomen, consistent with several days of untreated appendicitis. Estimated blood loss 200mL.

Post-op plan: ICU admission, continue IV antibiotics, NPO, NG tube decompression.

---

### Record 5 — Overlake Regional Medical Center — ICU Progress Note

**Date of Service:** 03/06/2026

POD#2. Patient with evolving sepsis post-op, on IV piperacillin-tazobactam, now also started on
vancomycin for broader coverage given persistent leukocytosis. Low-grade fever overnight, 100.9F max.
Hemodynamically stable, no pressor requirement. Abdominal drain output serosanguinous, decreasing.

Plan: Continue antibiotics, trend WBC and lactate, advance diet as tolerated when ileus resolves.

---

### Record 6 — Overlake Regional Medical Center — Discharge Summary

**Date of Service:** 03/11/2026

Discharge diagnosis: Perforated appendicitis with peritonitis and post-operative sepsis, resolved.

Hospital course: Total 7-day admission (03/04/2026–03/11/2026) including 2 days ICU-level care for
sepsis management. Completed 7-day course of IV antibiotics, transitioned to oral amoxicillin-
clavulanate for an additional 5 days at discharge. Surgical drain removed 03/09/2026 prior to
discharge.

Follow-up: Surgery clinic in 2 weeks. Primary care in 1 week.

---

### Record 7 — Crestline Urgent Care Group — Peer Review / Quality Note

**Date of Service:** 03/20/2026

Internal quality review note regarding the 03/02/2026 urgent care visit: chart notes right lower
quadrant tenderness was documented on exam but no imaging or lab work was ordered at that visit, and
no explicit instruction was given to follow up sooner than "if worsening." The 03/03/2026 telephone
triage note reflects reported worsening symptoms including inability to stand upright, which was
managed with continued conservative advice rather than a recommendation to be seen in person same-day.
