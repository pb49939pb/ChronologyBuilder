#!/usr/bin/env python3
"""
Generates case-folder-shaped test fixtures for Case Mode (see /case routes in webapp/app.py) — a
case's folder organized into subfolders (correspondence, depositions, discovery, experts, liens,
memo, orders, pleadings, records, team), with a Complaint/Notice of Intent in pleadings/ naming the
plaintiff/defendant(s)/date of loss/facts.

Two fixtures, on purpose:
- case_smith/: the normal path — a Complaint/NOI is present in pleadings/, and every subfolder has
  at least one file, so folder-wide recursive ingestion (not just "records/") is actually exercised.
- case_nodefendant/: the fallback path — no complaint/NOI anywhere, to confirm _find_complaint_file
  returning None surfaces a clear warning rather than blocking the case.

All content below is entirely fictional/synthetic — no real names, no real case data.
"""
import shutil
from pathlib import Path

from fpdf import FPDF

BASE = Path(__file__).resolve().parent.parent
SAMPLE_DATA = BASE / "sample_data"


def make_pdf(text: str, out_path: Path):
    """Plain, unstamped PDF — used only for the Complaint/NOI, which is parsed via a separate
    endpoint (_extract_complaint_info) that doesn't go through the citation-grounding/Bates flow
    at all, so it doesn't need one."""
    text = text.replace("—", "-").replace("–", "-")  # keep to latin-1, matching make_test_pdfs.py
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in text.split("\n"):
        pdf.write(6, line + "\n")
    pdf.output(str(out_path))


CASE_SMITH_BATES_PREFIX = "CS"
_POSITIONS = ("right", "left", "center")


class BatesPDF(FPDF):
    """Every OTHER_SUBFOLDER_DOCS file DOES go through the normal chronology-citation flow (Case
    Mode ingests every subfolder, not just records/), so those need a real Bates stamp — the app
    assumes every real PDF it processes has one (see _extract_bates_number in webapp/app.py)."""
    def __init__(self, bates_start: int, position: str):
        super().__init__()
        self.bates_start = bates_start
        self.bates_position = position

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        bates_str = f"{CASE_SMITH_BATES_PREFIX}{self.bates_start + self.page_no() - 1:06d}"
        if self.bates_position == "left":
            self.set_x(10)
            self.cell(40, 10, bates_str, align="L")
        elif self.bates_position == "center":
            self.set_x(0)
            self.cell(self.w, 10, bates_str, align="C")
        else:
            self.set_x(-50)
            self.cell(40, 10, bates_str, align="R")


def make_bates_pdf(text: str, out_path: Path, bates_start: int, position: str) -> int:
    text = text.replace("—", "-").replace("–", "-")
    pdf = BatesPDF(bates_start, position)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in text.split("\n"):
        pdf.write(6, line + "\n")
    pdf.output(str(out_path))
    return pdf.page_no()


COMPLAINT_TEXT = """SYNTHETIC TEST DATA - NOT A REAL CASE

IN THE CIRCUIT COURT, MEDICOLEGAL COUNTY

Jane Smith, Plaintiff,
v.
Dr. R. Okafor and Adeline Medical Center, Defendants.

COMPLAINT

1. This is an action for medical malpractice against Defendants Dr. R. Okafor and Adeline Medical
Center arising from care provided to Plaintiff Jane Smith.

2. On or about March 14, 2025 (the "Date of Loss"), Plaintiff presented to Adeline Medical Center
following right total knee arthroplasty performed by Dr. R. Okafor. Plaintiff alleges that
Defendants negligently delayed diagnosis and treatment of a pulmonary embolism despite documented
worsening shortness of breath and right calf discomfort in the days following surgery, resulting in
serious injury.

3. Plaintiff seeks damages for the injuries proximately caused by Defendants' negligence.

WHEREFORE, Plaintiff demands judgment against Defendants."""

# Minor placeholder documents for the non-"records" subfolders — just enough real text that
# recursive folder ingestion has something to read from every subfolder, per the instruction to
# ingest and analyze all files in the folder unless otherwise stated.
OTHER_SUBFOLDER_DOCS = {
    "correspondence": ("letter_to_defense_counsel.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

Re: Smith v. Okafor / Adeline Medical Center

Counsel,

This letter confirms receipt of the defendant's initial disclosures. We will follow up regarding
outstanding records requests under separate cover.
"""),
    "depositions": ("okafor_deposition_excerpt.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

DEPOSITION OF DR. R. OKAFOR (EXCERPT)

Q: Doctor, do you recall the post-operative course for Ms. Smith?
A: I recall she was discharged in stable condition on January 10, 2025.
"""),
    "discovery": ("interrogatory_responses.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

DEFENDANT'S RESPONSES TO PLAINTIFF'S FIRST SET OF INTERROGATORIES

Response to Interrogatory No. 1: Defendant Example Medical Center identifies the treating nursing
staff on duty from January 6-10, 2025 as previously disclosed in the medical records produced.
"""),
    "experts": ("expert_disclosure_summary.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

PLAINTIFF'S EXPERT WITNESS DISCLOSURE (SUMMARY)

Plaintiff intends to call a board-certified orthopedic surgeon to testify regarding the standard of
care for post-operative pulmonary embolism monitoring following total knee arthroplasty.
"""),
    "liens": ("hospital_lien_notice.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

NOTICE OF HOSPITAL LIEN

Example Medical Center asserts a lien against any settlement or judgment in this matter for unpaid
charges related to treatment provided to Jane Smith.
"""),
    "memo": ("case_strategy_memo.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

INTERNAL MEMO - CASE STRATEGY

Team: initial review of the medical records suggests the post-operative monitoring window (Jan 6-25,
2025) is the key period to focus the chronology on.
"""),
    "orders": ("scheduling_order.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

SCHEDULING ORDER

The Court sets the following deadlines: fact discovery to close in 120 days; expert disclosures 60
days thereafter.
"""),
    "team": ("team_assignments.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

TEAM ASSIGNMENTS

Paul: lead attorney. Olivia: chronology/medical record review. Associate: discovery responses.
"""),
}

SUBFOLDERS = (
    "correspondence", "depositions", "discovery", "experts", "liens",
    "memo", "orders", "pleadings", "records", "team",
)


def build_case_smith():
    """The normal path: a Complaint/NOI in pleadings/, records/ reuses case_001's existing medical
    record PDFs, and every other subfolder gets at least one file."""
    case_dir = SAMPLE_DATA / "case_smith"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    for sub in SUBFOLDERS:
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    make_pdf(COMPLAINT_TEXT, case_dir / "pleadings" / "complaint.pdf")

    records_src = SAMPLE_DATA / "case_001_pdfs"
    for src in sorted(records_src.glob("*.pdf")):
        shutil.copy2(src, case_dir / "records" / src.name)

    bates_counter = 1
    for i, (sub, (filename, text)) in enumerate(OTHER_SUBFOLDER_DOCS.items()):
        position = _POSITIONS[i % len(_POSITIONS)]
        pages_used = make_bates_pdf(text, case_dir / sub / filename, bates_counter, position)
        bates_counter += pages_used

    print(f"wrote {case_dir}")


FERREIRA_COMPLAINT_TEXT = """SYNTHETIC TEST DATA - NOT A REAL CASE

IN THE CIRCUIT COURT, MEDICOLEGAL COUNTY

Daniel R. Ferreira, Plaintiff,
v.
Dr. M. Castellano and Crestline Urgent Care, Defendants.

COMPLAINT

1. This is an action for medical malpractice against Defendants Dr. M. Castellano and Crestline
Urgent Care arising from care provided to Plaintiff Daniel R. Ferreira.

2. On or about March 2, 2026 (the "Date of Loss"), Plaintiff presented to Crestline Urgent Care
with abdominal pain later confirmed to be acute appendicitis. Plaintiff alleges that Defendants
negligently misdiagnosed his presentation as viral gastroenteritis and discharged him without
appropriate imaging or referral, delaying the correct diagnosis and treatment of his appendicitis
and resulting in a ruptured appendix and additional injury.

3. Plaintiff seeks damages for the injuries proximately caused by Defendants' negligence.

WHEREFORE, Plaintiff demands judgment against Defendants."""

FERREIRA_OTHER_SUBFOLDER_DOCS = {
    "correspondence": ("letter_to_defense_counsel.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

Re: Ferreira v. Castellano / Crestline Urgent Care

Counsel,

This letter confirms receipt of the defendant's initial disclosures regarding Mr. Ferreira's
urgent care visit. We will follow up regarding outstanding imaging records under separate cover.
"""),
    "depositions": ("castellano_deposition_excerpt.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

DEPOSITION OF DR. M. CASTELLANO (EXCERPT)

Q: Doctor, did you consider appendicitis as part of your differential for Mr. Ferreira?
A: Gastroenteritis was my leading diagnosis at the time, given his exam findings that day.
"""),
    "discovery": ("interrogatory_responses.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

DEFENDANT'S RESPONSES TO PLAINTIFF'S FIRST SET OF INTERROGATORIES

Response to Interrogatory No. 1: Defendant Crestline Urgent Care identifies the treating staff on
duty on March 2, 2026 as previously disclosed in the medical records produced.
"""),
    "experts": ("expert_disclosure_summary.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

PLAINTIFF'S EXPERT WITNESS DISCLOSURE (SUMMARY)

Plaintiff intends to call a board-certified emergency medicine physician to testify regarding the
standard of care for evaluating right lower quadrant abdominal pain in a young adult male.
"""),
    "liens": ("hospital_lien_notice.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

NOTICE OF HOSPITAL LIEN

Example Regional Hospital asserts a lien against any settlement or judgment in this matter for
unpaid charges related to treatment provided to Daniel R. Ferreira.
"""),
    "memo": ("case_strategy_memo.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

INTERNAL MEMO - CASE STRATEGY

Team: initial review suggests the March 2-3, 2026 window (the urgent care visit and the following
day's ED presentation) is the key period to focus the chronology on.
"""),
    "orders": ("scheduling_order.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

SCHEDULING ORDER

The Court sets the following deadlines: fact discovery to close in 120 days; expert disclosures 60
days thereafter.
"""),
    "team": ("team_assignments.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

TEAM ASSIGNMENTS

Paul: lead attorney. Olivia: chronology/medical record review. Associate: discovery responses.
"""),
}

WHITFIELD_COMPLAINT_TEXT = """SYNTHETIC TEST DATA - NOT A REAL CASE

IN THE CIRCUIT COURT, MEDICOLEGAL COUNTY

Linda K. Whitfield-Nakamura, Plaintiff,
v.
Dr. P. Adeyemi and Brightwater Cardiology Associates, Defendants.

COMPLAINT

1. This is an action for medical malpractice against Defendants Dr. P. Adeyemi and Brightwater
Cardiology Associates arising from care provided to Plaintiff Linda K. Whitfield-Nakamura.

2. On or about May 5, 2026 (the "Date of Loss"), Plaintiff was started on warfarin therapy for
newly-diagnosed atrial fibrillation. Plaintiff alleges that Defendants negligently mismanaged her
anticoagulation dosing and monitoring, failing to appropriately adjust her regimen in response to
her INR results, resulting in a bleeding complication.

3. Plaintiff seeks damages for the injuries proximately caused by Defendants' negligence.

WHEREFORE, Plaintiff demands judgment against Defendants."""

WHITFIELD_OTHER_SUBFOLDER_DOCS = {
    "correspondence": ("letter_to_defense_counsel.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

Re: Whitfield-Nakamura v. Adeyemi / Brightwater Cardiology Associates

Counsel,

This letter confirms receipt of the defendant's initial disclosures regarding Ms.
Whitfield-Nakamura's anticoagulation management. We will follow up regarding outstanding lab
records under separate cover.
"""),
    "depositions": ("adeyemi_deposition_excerpt.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

DEPOSITION OF DR. P. ADEYEMI (EXCERPT)

Q: Doctor, how frequently should INR have been monitored after starting warfarin?
A: Typically weekly at first, adjusting the dose based on each result.
"""),
    "discovery": ("interrogatory_responses.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

DEFENDANT'S RESPONSES TO PLAINTIFF'S FIRST SET OF INTERROGATORIES

Response to Interrogatory No. 1: Defendant Brightwater Cardiology Associates identifies the
treating staff involved in Ms. Whitfield-Nakamura's anticoagulation management as previously
disclosed in the medical records produced.
"""),
    "experts": ("expert_disclosure_summary.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

PLAINTIFF'S EXPERT WITNESS DISCLOSURE (SUMMARY)

Plaintiff intends to call a board-certified cardiologist to testify regarding the standard of care
for warfarin dosing and INR monitoring following new-onset atrial fibrillation.
"""),
    "liens": ("hospital_lien_notice.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

NOTICE OF HOSPITAL LIEN

Example Regional Hospital asserts a lien against any settlement or judgment in this matter for
unpaid charges related to treatment provided to Linda K. Whitfield-Nakamura.
"""),
    "memo": ("case_strategy_memo.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

INTERNAL MEMO - CASE STRATEGY

Team: initial review suggests the anticoagulation dosing/monitoring window following May 5, 2026
is the key period to focus the chronology on, including the documented INR discrepancy.
"""),
    "orders": ("scheduling_order.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

SCHEDULING ORDER

The Court sets the following deadlines: fact discovery to close in 120 days; expert disclosures 60
days thereafter.
"""),
    "team": ("team_assignments.pdf", """SYNTHETIC TEST DATA - NOT A REAL CASE

TEAM ASSIGNMENTS

Paul: lead attorney. Olivia: chronology/medical record review. Associate: discovery responses.
"""),
}


def _build_full_case(case_name, complaint_text, other_docs, records_src_name, bates_prefix):
    """Shared builder for the case_smith-shaped fixtures below — same 10-subfolder structure, a
    Complaint/NOI in pleadings/, records/ populated from an existing (already Bates-stamped)
    case_00X_pdfs fixture, and every other subfolder gets a Bates-stamped placeholder file with
    text specific to THIS case (not case_smith's boilerplate) so each fixture has genuinely
    different content, not just a renamed copy."""
    case_dir = SAMPLE_DATA / case_name
    if case_dir.exists():
        shutil.rmtree(case_dir)
    for sub in SUBFOLDERS:
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    make_pdf(complaint_text, case_dir / "pleadings" / "complaint.pdf")

    records_src = SAMPLE_DATA / records_src_name
    for src in sorted(records_src.glob("*.pdf")):
        shutil.copy2(src, case_dir / "records" / src.name)

    class _CaseBatesPDF(FPDF):
        _bates_start = 1
        _bates_position = "right"

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", size=9)
            bates_str = f"{bates_prefix}{self._bates_start + self.page_no() - 1:06d}"
            if self._bates_position == "left":
                self.set_x(10)
                self.cell(40, 10, bates_str, align="L")
            elif self._bates_position == "center":
                self.set_x(0)
                self.cell(self.w, 10, bates_str, align="C")
            else:
                self.set_x(-50)
                self.cell(40, 10, bates_str, align="R")

    bates_counter = 1
    for i, (sub, (filename, text)) in enumerate(other_docs.items()):
        position = _POSITIONS[i % len(_POSITIONS)]
        text = text.replace("—", "-").replace("–", "-")
        pdf = _CaseBatesPDF()
        pdf._bates_start = bates_counter
        pdf._bates_position = position
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        for line in text.split("\n"):
            pdf.write(6, line + "\n")
        pdf.output(str(case_dir / sub / filename))
        bates_counter += pdf.page_no()

    print(f"wrote {case_dir} (records from {records_src_name})")


def build_case_ferreira():
    """Second case_smith-shaped fixture — different plaintiff/defendant/facts (delayed appendicitis
    diagnosis rather than post-op PE), records/ reuses the existing case_002_pdfs fixture (already
    Bates-stamped, and its patient name — Daniel R. Ferreira — matches this case's plaintiff)."""
    _build_full_case(
        "case_ferreira", FERREIRA_COMPLAINT_TEXT, FERREIRA_OTHER_SUBFOLDER_DOCS,
        "case_002_pdfs", "FER",
    )


def build_case_whitfield():
    """Third case_smith-shaped fixture — different again (anticoagulation dosing error), records/
    reuses the existing case_003_pdfs fixture (already Bates-stamped, patient name matches, and it
    deliberately contains a real discrepancy — useful variety for the highlighting regression
    test, which shouldn't only ever see clean single-source findings)."""
    _build_full_case(
        "case_whitfield", WHITFIELD_COMPLAINT_TEXT, WHITFIELD_OTHER_SUBFOLDER_DOCS,
        "case_003_pdfs", "WHIT",
    )


def build_case_nodefendant():
    """The fallback path: no complaint/NOI anywhere in the folder — confirms the app proceeds with
    a clear warning instead of blocking the case."""
    case_dir = SAMPLE_DATA / "case_nodefendant"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    (case_dir / "records").mkdir(parents=True, exist_ok=True)

    records_src = SAMPLE_DATA / "case_002_pdfs"
    for src in sorted(records_src.glob("*.pdf")):
        shutil.copy2(src, case_dir / "records" / src.name)

    print(f"wrote {case_dir}")


if __name__ == "__main__":
    build_case_smith()
    build_case_ferreira()
    build_case_whitfield()
    build_case_nodefendant()
