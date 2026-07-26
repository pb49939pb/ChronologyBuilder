#!/usr/bin/env python3
"""
Generates a small, mixed-patient test folder for the batch-folder feature (see /batch routes in
webapp/app.py). Unlike the existing per-case sample_data fixtures, each document here embeds
patient-identifying text directly in its own body — matching how real EHR exports actually work
(confirmed on the real "Visit Summary" documents referenced in TEST_RESULTS.md) — which the
existing single-case fixtures deliberately don't do, since they were built before patient-grouping
was a requirement.

Three fictional, entirely synthetic patients, using two different identity-field formats on
purpose (one "Patient Name:", one "Last Name:/First Name:") so the test exercises both regex
patterns _extract_patient_identity looks for — plus one deliberately unidentifiable document (no
patient fields at all) to confirm the "Unidentified" bucket works rather than crashing or silently
dropping it.
"""
from pathlib import Path

from fpdf import FPDF

BASE = Path(__file__).resolve().parent.parent
OUT_DIR = BASE / "sample_data" / "batch_test_folder"


DOCS = [
    # Patient A — Maria Gonzalez — 2 documents, "Patient Name:" format
    ("patientA_visit1.pdf", """SYNTHETIC TEST DATA - NOT A REAL PATIENT

Crestline Family Medicine - Office Visit
Patient Name: Maria Gonzalez
DOB: 05/12/1985
Date of Service: 02/10/2026
Provider: Dr. R. Simmons

Chief complaint: Annual physical.
Assessment: Generally healthy. Continue current medications.
Plan: Return in one year, or sooner if new symptoms arise."""),
    ("patientA_visit2.pdf", """SYNTHETIC TEST DATA - NOT A REAL PATIENT

Crestline Family Medicine - Follow-up Visit
Patient Name: Maria Gonzalez
DOB: 05/12/1985
Date of Service: 04/22/2026
Provider: Dr. R. Simmons

Chief complaint: Follow-up for elevated blood pressure noted at last visit.
Exam: BP 148/92. Repeat 144/90.
Assessment: New diagnosis of hypertension.
Plan: Start lisinopril 10mg daily. Recheck in one month."""),
    # Patient B — Thomas Reyes — 2 documents, "Last Name:/First Name:" format (matches the real
    # EHR export pattern seen in TEST_RESULTS.md)
    ("patientB_er_note.pdf", """SYNTHETIC TEST DATA - NOT A REAL PATIENT

Riverside Emergency Department - Visit Summary
Last Name: Reyes    First Name: Thomas
DOB: 11/03/1972
Date of Service: 01/15/2026
Provider: Dr. K. Whitfield

Chief complaint: Chest pain.
Exam: EKG shows normal sinus rhythm. Troponin negative x2.
Assessment: Atypical chest pain, likely musculoskeletal. Cardiac workup negative.
Plan: Discharge home. Follow up with cardiology as outpatient."""),
    ("patientB_cardiology_followup.pdf", """SYNTHETIC TEST DATA - NOT A REAL PATIENT

Riverside Cardiology Associates - Consultation Note
Last Name: Reyes    First Name: Thomas
DOB: 11/03/1972
Date of Service: 02/02/2026
Provider: Dr. S. Okonkwo

Chief complaint: Follow-up after ER visit for chest pain.
Exam: Stress echocardiogram performed, no ischemic changes noted.
Assessment: Non-cardiac chest pain confirmed. No evidence of coronary artery disease.
Plan: Reassurance. No further cardiac workup needed at this time."""),
    # An unidentifiable document -- no patient fields at all -- to confirm the "Unidentified"
    # bucket works rather than crashing or being silently dropped.
    ("unlabeled_lab_slip.pdf", """SYNTHETIC TEST DATA - NOT A REAL PATIENT

Quick Lab Services - Result Slip

Test: Basic Metabolic Panel
Result: All values within normal limits.
No patient identifying information printed on this particular slip format."""),
]


BATES_PREFIX = "BTF"
_POSITIONS = ("right", "left", "center")


class BatesPDF(FPDF):
    """Stamps a sequential Bates number in the bottom margin of every page — the app assumes every
    real PDF it processes has one (see _extract_bates_number in webapp/app.py), so test data needs
    one too for that assumption to actually be exercised. Position rotates across documents to
    cover left/center/right placement, matching real productions where it varies."""
    def __init__(self, bates_start: int, position: str):
        super().__init__()
        self.bates_start = bates_start
        self.bates_position = position

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        bates_str = f"{BATES_PREFIX}{self.bates_start + self.page_no() - 1:06d}"
        if self.bates_position == "left":
            self.set_x(10)
            self.cell(40, 10, bates_str, align="L")
        elif self.bates_position == "center":
            self.set_x(0)
            self.cell(self.w, 10, bates_str, align="C")
        else:
            self.set_x(-50)
            self.cell(40, 10, bates_str, align="R")


def make_pdf(text: str, out_path: Path, bates_start: int, position: str) -> int:
    text = text.replace("—", "-").replace("–", "-")  # keep to latin-1, matching make_test_pdfs.py
    pdf = BatesPDF(bates_start, position)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in text.split("\n"):
        pdf.write(6, line + "\n")
    pdf.output(str(out_path))
    return pdf.page_no()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bates_counter = 1
    for i, (filename, text) in enumerate(DOCS):
        out_path = OUT_DIR / filename
        position = _POSITIONS[i % len(_POSITIONS)]
        pages_used = make_pdf(text, out_path, bates_counter, position)
        bates_counter += pages_used
        print(f"wrote {out_path} (bates {position})")


if __name__ == "__main__":
    main()
