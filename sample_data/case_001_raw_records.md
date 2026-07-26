# SYNTHETIC TEST DATA — NOT A REAL PATIENT

This file is entirely fictional, written for testing the LawFirmAgent extraction pipeline. No real
patient, provider, or facility is represented. Patient name, MRN, DOB, and all provider names below
are invented. This is the kind of raw, multi-source document bundle a paralegal would actually
receive (several separate notes from different visits/providers, not yet organized into a
chronology) — the task for the model is to build an accurate chronology *from* this.

---

**Patient:** Margaret A. Sullivan
**MRN:** SYN-00417 (synthetic)
**DOB:** 04/02/1961

---

### Record 1 — Fairview Orthopedic Surgery Center — Operative Report

**Date of Service:** 01/06/2025
**Surgeon:** Dr. R. Okafor

Pre-operative diagnosis: Right knee osteoarthritis, end-stage. Patient with documented history of
Factor V Leiden mutation (heterozygous), noted in pre-op hematology clearance dated 12/18/2024.

Procedure: Right total knee arthroplasty (TKA), uncomplicated. Estimated blood loss 150mL. Patient
tolerated procedure well.

Post-op orders: Enoxaparin 40mg subcutaneous once daily for DVT prophylaxis, to begin post-op day 1.
Standard post-op physical therapy protocol. Weight-bearing as tolerated.

---

### Record 2 — Fairview Orthopedic Surgery Center — Post-Op Progress Note

**Date of Service:** 01/07/2025
**Provider:** Dr. R. Okafor

POD#1. Patient reports pain 4/10, controlled with oral analgesics. Mild edema and swelling noted in
right calf, consistent with expected post-surgical changes. No erythema, no calf tenderness on
palpation. Wound clean, dry, intact. Continue enoxaparin 40mg SC daily. Plan to discharge home when
PT clears for stairs.

---

### Record 3 — Fairview Orthopedic Surgery Center — Discharge Summary

**Date of Service:** 01/10/2025
**Discharging Provider:** Dr. R. Okafor

Discharged home in stable condition, POD#4. Discharge medications: enoxaparin 40mg SC daily to
continue for 14 days total post-op, plus acetaminophen and oxycodone PRN for pain. Instructed to
follow up with PCP in one week and to return sooner if experiencing chest pain, shortness of breath,
or worsening leg swelling.

---

### Record 4 — Riverbend Family Medicine — Office Visit

**Date of Service:** 01/15/2025
**Provider:** Dr. L. Voss (PCP)

Chief complaint: f/u post-op.

Patient here for routine post-surgical follow-up per ortho instructions. Reports right knee incision
healing well. Reports "some tightness" in the calf and getting winded more easily than usual, which
she attributes to being less active than normal during recovery. No chest pain reported. Denies
fever.

Exam: right knee incision clean/healing, mild residual swelling of right lower extremity, not
tender. Lungs clear to auscultation.

Assessment: Normal post-operative recovery, mild deconditioning. Plan: continue home exercise
program, no imaging indicated at this time. Return to clinic in 4 weeks or sooner if symptoms
worsen.

---

### Record 5 — Fairview Orthopedic Surgery Center — Physical Therapy Note

**Date of Service:** 01/19/2025
**Provider:** J. Marsh, PT

Patient attending outpatient PT, POD#13. Working on ROM and strengthening. Patient reports she has
"been short of breath for about the last week," worse with exertion, and that her right calf
"still feels tight and achy." Advised patient to follow up with her physician regarding the
shortness of breath. Continued today's session as tolerated; patient fatigued more quickly than
prior visits.

---

### Record 6 — St. Adeline Medical Center — Emergency Department Note

**Date of Service:** 01/21/2025
**Provider:** Dr. K. Ibrahim, Emergency Medicine

Chief complaint: Acute shortness of breath, arrived via EMS.

HPI: 63-year-old female, s/p right TKA on 01/06/2025, presents with acute-onset severe shortness of
breath and right-sided chest pain that began approximately 2 hours prior to arrival. Patient reports
several days of worsening exertional dyspnea and persistent right calf discomfort since her prior
surgery, which she had reported to her physical therapist and, less specifically, to her PCP.

Vitals: HR 128, BP 102/68, RR 28, SpO2 89% on room air, Temp 98.9F.

Exam: Tachycardic, tachypneic, mild hypoxia. Right calf with mild swelling and tenderness. No
edema on left.

CT angiogram chest: Bilateral pulmonary emboli, moderate clot burden, no evidence of right heart
strain at this time.

Assessment: Acute bilateral pulmonary embolism, likely secondary to right lower extremity DVT in the
setting of recent TKA and known Factor V Leiden mutation.

Plan: Admit to ICU. Start IV unfractionated heparin drip. Hematology and cardiology consults placed.

---

### Record 7 — St. Adeline Medical Center — ICU Admission / Hematology Consult Note

**Date of Service:** 01/22/2025
**Provider:** Dr. S. Whitfield, Hematology

Consulted for management of acute PE in patient with known heterozygous Factor V Leiden mutation
(documented 12/18/2024 pre-op hematology clearance). Patient's post-operative DVT prophylaxis
(enoxaparin 40mg daily) was a standard prophylactic dose; given her known thrombophilia, a higher
index of suspicion for VTE was warranted with her reported symptoms of dyspnea and persistent calf
discomfort in the two weeks following surgery.

Currently on IV heparin drip, therapeutic PTT achieved as of this morning. Plan to transition to
oral apixaban 10mg twice daily for 7 days, then 5mg twice daily thereafter, once stable for
discharge.

---

### Record 8 — St. Adeline Medical Center — Discharge Summary

**Date of Service:** 01/25/2025
**Discharging Provider:** Dr. S. Whitfield

Discharge diagnosis: Bilateral pulmonary emboli, resolved right lower extremity DVT (confirmed by
venous ultrasound on 01/23/2025), in patient with known Factor V Leiden mutation, following recent
right TKA.

Hospital course: Improved on IV heparin, transitioned to apixaban 10mg BID as above. Ambulatory,
oxygen-independent at discharge.

Discharge medications: Apixaban 10mg PO BID x 7 days, then 5mg PO BID ongoing (duration to be
determined by hematology follow-up). Discontinue enoxaparin.

Follow-up: Hematology in 2 weeks, cardiology in 4 weeks, PCP in 1 week.

---

### Record 9 — Riverbend Family Medicine — Office Visit

**Date of Service:** 02/01/2025
**Provider:** Dr. L. Voss (PCP)

Chief complaint: f/u after hospitalization for PE.

Patient seen for follow-up after recent hospitalization. Doing well, ambulating without shortness of
breath. Continuing apixaban per hematology. Reviewed hospital course with patient. No new
complaints today.
