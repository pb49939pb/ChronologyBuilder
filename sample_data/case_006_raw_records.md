# SYNTHETIC TEST DATA — NOT A REAL PATIENT

This file is entirely fictional, written for testing the LawFirmAgent extraction pipeline. No real
patient, provider, or facility is represented.

**Built 2026-08-02 specifically to be MORE representative of real-world document messiness than the
earlier synthetic cases** — a real user test surfaced that the app reliably extracts simple
structured facts (labs, radiology values) but was missing whole visit-summary narratives, and never
filled in demographics (social/family/surgical history) even when the information genuinely existed
somewhere in the record set. This case deliberately embeds those exact conditions to make the
problem reproducible without needing real PHI:
- Several full visit-note narratives (chief complaint / HPI / ROS / exam / plan / prescriptions),
  matching real dictated-note structure, not a clean bulleted template.
- Demographic details (smoking status, family history, prior surgery, PCP) planted as PASSING
  ASIDES inside visit narratives — never under a clean labeled "Social History:" heading — since
  that's how they actually tend to appear in real records.
- Provider credentials deliberately varied (MD, DO, PT, NP) across different visit types, so a
  reader can't assume every "visit" is with a physician.
- A couple of structured lab/radiology reports mixed in, so the test also confirms visits aren't
  crowded out once those simpler categories are present.

Fact pattern: a fall at work leads to a delayed rotator cuff tear diagnosis — physical therapy
started before imaging, imaging delayed, tear found late.

---

**Patient:** Robert T. Ashworth
**MRN:** SYN-00612 (synthetic)
**DOB:** 03/14/1971

---

### Record 1 — Meridian Occupational Health — Initial Visit

**Date of Service:** 02/03/2026
**Provider:** Dr. A. Kowalski, DO

Patient presents after a fall at work yesterday, landing on outstretched right arm. Reports right
shoulder pain, worse with overhead reaching. Denies numbness/tingling in the hand.

Past medical history notable for hypertension, well-controlled on lisinopril. Patient mentions he
had his gallbladder removed "a few years back" without complication.

ROS: denies fever, chest pain, shortness of breath. Reports occasional low back stiffness, longstanding.

Physical exam:
Right shoulder: tenderness over lateral deltoid, painful arc of abduction 60-120 degrees, weakness
with resisted external rotation. Neurovascularly intact distally.

Assessment: Right shoulder strain, rule out rotator cuff injury.

Plan: Conservative management for 2 weeks — NSAIDs, activity modification. Refer to physical
therapy. If no improvement, will order MRI. Follow up in 2 weeks.

Prescriptions Written Today: Meloxicam 15mg PO once daily for 14 days.

---

### Record 2 — Cascade Physical Therapy — Initial PT Evaluation

**Date of Service:** 02/10/2026
**Provider:** Melissa Tran, PT, DPT

Patient referred by Dr. Kowalski for right shoulder pain s/p fall. Patient reports pain 6/10 at
rest, 8/10 with overhead activity. Works as a warehouse supervisor, reports difficulty lifting boxes
overhead at work.

Patient notes he is a former smoker, quit approximately 8 years ago, previously about a pack a day
for 15 years.

Objective: Right shoulder AROM flexion 110 degrees (limited by pain), abduction 95 degrees. Positive
Hawkins-Kennedy impingement sign. Positive empty can test with pain, though strength difficult to
fully assess secondary to pain.

Assessment: Right shoulder impingement syndrome, subacromial. Findings also consistent with possible
rotator cuff pathology — recommend patient follow up with referring provider regarding imaging if
not already planned.

Plan: Begin PT 2x/week — pendulum exercises, subacromial mobilization, progressive strengthening
once acute pain subsides. Reassess in 2 weeks.

---

### Record 3 — Cascade Physical Therapy — Progress Note

**Date of Service:** 02/24/2026
**Provider:** Melissa Tran, PT, DPT

Patient completed 4 PT visits. Reports minimal improvement in overhead function, pain persists at
6-7/10 with overhead reaching. Strength testing today: 4-/5 resisted external rotation with pain,
4/5 resisted abduction with pain, both notably weaker than typical strain presentation at this
stage of treatment.

Assessment: Persistent impingement symptoms, poor response to 4 visits of conservative PT. Weakness
on manual muscle testing raises concern for a structural rotator cuff tear rather than simple
strain/impingement alone.

Plan: Recommend patient return to referring provider to discuss advancing workup (MRI) given lack of
expected progress with conservative care. Will continue PT in the meantime.

---

### Record 4 — Meridian Occupational Health — Follow-Up Visit

**Date of Service:** 03/03/2026
**Provider:** Dr. A. Kowalski, DO

Patient returns, referred back by physical therapy given lack of progress after 6 visits. Continues
to report right shoulder pain with overhead activity, now also reporting some night pain waking him
from sleep, new since last visit.

Patient's mother had a hip replacement in her 60s; patient unsure of the underlying cause.

Physical exam: Persistent painful arc, positive impingement signs, subjective weakness with resisted
external rotation.

Assessment: Right shoulder pain, not improved with 6 weeks conservative management including PT.

Plan: Will order MRI right shoulder without contrast to further evaluate for rotator cuff pathology.
Continue current PT program pending imaging.

---

### Record 5 — Cascade Physical Therapy — Progress Note

**Date of Service:** 03/10/2026
**Provider:** Melissa Tran, PT, DPT

Patient continues PT, now 8 visits total. Reports ongoing night pain, difficulty sleeping on right
side. States MRI has been ordered by Dr. Kowalski but not yet scheduled due to insurance
authorization delay per patient report.

Assessment: Continued impingement-pattern symptoms with persistent weakness, unresolved after 8
visits — again noting these findings are atypical for simple impingement without a structural tear.

Plan: Continue PT, defer further plan changes pending MRI results.

---

### Record 6 — Ridgeline Diagnostic Imaging — MRI Report

**Date of Service:** 04/02/2026
**Ordering Provider:** Dr. A. Kowalski, DO
**Reading Provider:** Dr. F. Oyelaran, MD (Radiology)

MRI RIGHT SHOULDER WITHOUT CONTRAST

CLINICAL HISTORY: Right shoulder pain following fall, 8 weeks conservative treatment without
improvement.

FINDINGS: Full-thickness tear of the supraspinatus tendon, approximately 1.5 cm, with mild
retraction. Moderate subacromial-subdeltoid bursitis. Mild AC joint degenerative changes. No
significant muscle atrophy.

IMPRESSION: Full-thickness supraspinatus tear, approximately 1.5cm.

---

### Record 7 — Meridian Occupational Health — Follow-Up Visit

**Date of Service:** 04/09/2026
**Provider:** Dr. A. Kowalski, DO

Patient returns to review MRI results. Findings discussed — full-thickness rotator cuff tear.
Patient reports continued significant functional limitation, unable to perform overhead lifting
required for his job duties.

Patient mentions his father had "some kind of shoulder surgery" years ago, unclear on details.

Assessment: Full-thickness right supraspinatus tear, confirmed by MRI, approximately 9 weeks after
initial injury and symptom onset.

Plan: Referral to orthopedic surgery for evaluation and likely surgical repair given full-thickness
tear and failure of conservative management. Continue current activity restrictions.

---

### Record 8 — Alpine Orthopedic Surgery — New Patient Consultation

**Date of Service:** 04/23/2026
**Provider:** Dr. R. Whitfield, MD

Patient referred by Dr. Kowalski for full-thickness right rotator cuff tear on MRI, now
approximately 11 weeks after injury.

HPI as above. Patient reports significant impact on activities of daily living and inability to
perform his usual work duties. Notes he lives alone and has had to rely on a neighbor for help with
household tasks requiring overhead reaching.

Physical exam: Positive drop arm test. Weakness with resisted external rotation, 3/5. Painful arc.
MRI reviewed, confirms full-thickness supraspinatus tear with mild retraction.

Assessment: Full-thickness right rotator cuff (supraspinatus) tear, now chronic given delay to
diagnosis, with mild tendon retraction noted on imaging.

Plan: Discussed surgical repair options given failure of conservative management and imaging
findings. Risks of delayed repair discussed, including increased risk of retraction, fatty
infiltration, and potentially more limited surgical options/outcomes the longer repair is delayed.
Patient elects to proceed with surgical repair. Surgery scheduled.

Prescriptions Written Today: None today; pre-operative instructions provided.

---

### Record 9 — Alpine Orthopedic Surgery — Operative Report

**Date of Service:** 05/12/2026
**Surgeon:** Dr. R. Whitfield, MD

PREOPERATIVE DIAGNOSIS: Full-thickness right rotator cuff (supraspinatus) tear.
POSTOPERATIVE DIAGNOSIS: Same, with moderate tendon retraction and fraying noted intraoperatively,
more advanced than typical for an acute tear given the delay to surgical repair.

PROCEDURE: Right shoulder arthroscopy with rotator cuff repair.

FINDINGS: Full-thickness supraspinatus tear confirmed, moderate retraction requiring extensive
mobilization to achieve primary repair. Mild-to-moderate fatty infiltration of the supraspinatus
muscle belly noted. Repair performed successfully using suture anchor technique.

Patient tolerated the procedure well.

---

### Record 10 — Alpine Orthopedic Surgery — Post-Operative Follow-Up

**Date of Service:** 06/02/2026
**Provider:** Dr. R. Whitfield, MD

Patient 3 weeks status post right rotator cuff repair. Incisions healing well. Reports pain
improving, currently in sling per protocol.

Discussed with patient that given the moderate retraction and fatty infiltration found at surgery —
findings consistent with a tear that had been present for some time prior to repair — his ultimate
recovery and strength may be somewhat more limited than would be expected from a more acute repair.

Plan: Begin post-operative physical therapy per protocol. Continue sling per surgeon instructions.
Follow up in 6 weeks.
