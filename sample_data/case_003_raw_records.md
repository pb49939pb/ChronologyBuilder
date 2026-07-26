# SYNTHETIC TEST DATA — NOT A REAL PATIENT

This file is entirely fictional, written for testing the LawFirmAgent extraction pipeline. No real
patient, provider, or facility is represented. A third fact pattern (anticoagulation dosing error)
for test variety — and unlike Case 001/002, this one contains a REAL discrepancy that should be
flagged, to test that the model doesn't become so conservative about false positives that it misses
genuine conflicts too.

---

**Patient:** Linda K. Whitfield-Nakamura
**MRN:** SYN-01203 (synthetic)
**DOB:** 11/29/1958

---

### Record 1 — Brightwater Cardiology Associates — Office Visit

**Date of Service:** 05/05/2026
**Provider:** Dr. P. Adeyemi

Chief complaint: Palpitations.

HPI: 67-year-old female with new-onset atrial fibrillation confirmed on ECG and 24-hour monitor.
CHA2DS2-VASc score 4, indicating anticoagulation is warranted.

Assessment: New-onset atrial fibrillation.

Plan: Start warfarin 5mg PO once daily. INR check in 1 week to guide dose titration. Discussed
bleeding risk and need for consistent dosing with patient.

---

### Record 2 — Sunridge Home Health Services — Medication Administration Record (excerpt)

**Dates Covered:** 05/06/2026 through 05/10/2026

Warfarin 10mg PO administered daily, per home health aide documentation, days 1 through 5. Patient
reports taking "the pills the nurse set out" each morning as instructed.

---

### Record 3 — Brightwater Cardiology Associates — Lab Result / Telephone Note

**Date of Service:** 05/12/2026

INR result: 6.8 (therapeutic range 2.0–3.0 for atrial fibrillation). Critically elevated.

Note in chart: "Lab called with critical INR value. Message left for patient to hold next dose and
call clinic." No documentation of a return call from patient or clinic follow-up contact found in
the remainder of this record.

---

### Record 4 — Overlake Regional Medical Center — Emergency Department Note

**Date of Service:** 05/14/2026

Chief complaint: Blood in stool, dizziness.

HPI: 67-year-old female on warfarin for atrial fibrillation, presents with 1 day of melena and
lightheadedness. Reports she "never got a call back" after a lab a few days ago but did not follow up
herself either.

Labs: INR 8.4, Hemoglobin 7.1 (baseline reportedly ~13 per patient). 

Assessment: Upper GI bleed, supratherapeutic INR, likely warfarin-related.

Plan: Admit. Reverse anticoagulation, transfuse, GI consult for endoscopy.

---

### Record 5 — Overlake Regional Medical Center — Hospital Course / Admission Note

**Date of Service:** 05/14/2026
**Provider:** Dr. R. Salazar, Hospitalist

Reviewed home medication administration records showing warfarin 10mg daily was given for the first
5 days after starting therapy, rather than the 5mg daily dose ordered at the initiating cardiology
visit. This dosing discrepancy likely contributed to the supratherapeutic INR and subsequent bleed.

Plan: Vitamin K and 4-factor prothrombin complex concentrate given for reversal. 2 units packed red
blood cells transfused. GI consulted for endoscopy given melena and significant hemoglobin drop.

---

### Record 6 — Overlake Regional Medical Center — GI Consult / Endoscopy Note

**Date of Service:** 05/15/2026

Upper endoscopy performed: duodenal ulcer with visible vessel, treated with clip placement and
epinephrine injection. Hemostasis achieved.

Plan: Hold anticoagulation for now, cardiology to advise on resuming once GI bleed resolved.

---

### Record 7 — Overlake Regional Medical Center — Discharge Summary

**Date of Service:** 05/19/2026

Discharge diagnosis: Upper GI bleed secondary to supratherapeutic INR from a warfarin dosing error
(10mg administered vs. 5mg ordered), duodenal ulcer with successful endoscopic hemostasis.

Hospital course: 5-day admission, transfused 2 units PRBC, reversed anticoagulation, endoscopic
treatment of bleeding ulcer, hemoglobin stable at discharge (10.9).

Discharge medications: Apixaban 5mg PO BID (switched from warfarin given the dosing/monitoring
complexity). Medication list reviewed line-by-line with patient and home health agency contacted to
correct prior administration error.

Follow-up: Cardiology in 1 week, GI in 4 weeks, repeat hemoglobin check in 1 week via primary care.
