"""Generate the sample PDFs that the demo seed attaches to applications.

The files are deliberately small, fictional documents. A handful are flawed on
purpose so the document-verification step has something to reject:

* an expired fire safety certificate,
* a Digital Signature Certificate upload without a signature,
* an affidavit with a name that does not match the institution,
* a blank scan.

They are written under ``settings.storage_dir/demo`` and referenced by
``Document.storage_path``. Generation is skipped when the file already exists,
so re-running the seed stays fast.
"""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger("app.demo_documents")

DEMO_DIR = "demo"

# logical name -> (title, filename, body)
_DOCUMENTS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "fire_safety_expired",
        "Fire Safety Certificate (expired)",
        "fire_safety_certificate_expired.pdf",
        (
            "This certificate was issued to a fictional institution for demo purposes.",
            "Certificate number: FIRE/DEMO/2024/017",
            "Valid until: 31 December 2025",
            "The certificate has expired. The scrutiny officer rejects it under APH 1.8f.",
        ),
    ),
    (
        "fire_safety_valid",
        "Fire Safety Certificate",
        "fire_safety_certificate_valid.pdf",
        (
            "This certificate was issued to a fictional institution for demo purposes.",
            "Certificate number: FIRE/DEMO/2026/041",
            "Valid until: 31 March 2028",
        ),
    ),
    (
        "dsc_unsigned",
        "Digital Signature Certificate",
        "dsc_certificate_unsigned.pdf",
        (
            "Fictional Digital Signature Certificate printout.",
            "The upload carries no digital signature, so it cannot be verified (APH 1.4.3).",
        ),
    ),
    (
        "affidavit_name_mismatch",
        "Affidavit 3 - Name mismatch",
        "affidavit_3_name_mismatch.pdf",
        (
            "Fictional Affidavit 3 submitted with the application.",
            "Institution on the portal: Vidya Vikas College of Engineering (Fictional).",
            "Institution on the affidavit: Vidya Vikas Institute of Technology.",
            "The names differ; the document is flagged for a name mismatch.",
        ),
    ),
    (
        "blank_scan",
        "Blank scan",
        "blank_scan.pdf",
        (),
    ),
    (
        "land_document",
        "Land ownership document",
        "land_ownership_document.pdf",
        (
            "Fictional land ownership extract for the demo dataset.",
            "Plot area: 2.4 acres. Ownership: trust owned. No encumbrance.",
        ),
    ),
    (
        "building_plan",
        "Approved building plan",
        "building_plan_approval.pdf",
        (
            "Fictional approved building plan for the demo dataset.",
            "Built-up area: 8,450 sq. m. Sanctioned by the municipal authority.",
        ),
    ),
    (
        "faculty_list",
        "Faculty list",
        "faculty_list.pdf",
        (
            "Fictional faculty list for the demo dataset.",
            "The roster is illustrative and does not describe a real institution.",
        ),
    ),
    (
        "audit_report",
        "Audited statement of accounts",
        "audited_statement_of_accounts.pdf",
        (
            "Fictional audited statement of accounts for the demo dataset.",
            "The figures are illustrative only.",
        ),
    ),
    (
        "mandatory_disclosure",
        "Mandatory disclosure",
        "mandatory_disclosure.pdf",
        (
            "Fictional mandatory disclosure published by the institution.",
            "The document is illustrative and does not describe a real institution.",
        ),
    ),
)

# Relative path for each logical document name.
_DOC_PATHS: dict[str, str] = {
    key: f"{DEMO_DIR}/{filename}" for key, _title, filename, _body in _DOCUMENTS
}


def demo_document_paths() -> dict[str, str]:
    """Return ``{logical_name: storage_path}`` without generating the files."""
    return dict(_DOC_PATHS)


def ensure_demo_documents(storage_dir: Path | str) -> dict[str, str]:
    """Create the fictional demo PDFs and return their storage paths."""
    root = Path(storage_dir) / DEMO_DIR
    root.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DemoTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "DemoBody",
        parent=styles["BodyText"],
        fontSize=11,
        leading=16,
    )
    footer_style = ParagraphStyle(
        "DemoFooter",
        parent=styles["BodyText"],
        fontSize=8,
        textColor=colors.grey,
    )

    for key, title, filename, body in _DOCUMENTS:
        target = root / filename
        if target.is_file():
            continue
        story: list[object] = [Paragraph(title, title_style)]
        story.append(
            Paragraph(
                "Fictional document generated for the Smart India Hackathon demo. "
                "It does not relate to a real institution.",
                footer_style,
            )
        )
        story.append(Spacer(1, 8 * mm))
        if body:
            for line in body:
                story.append(Paragraph(line, body_style))
                story.append(Spacer(1, 3 * mm))
        else:
            # A blank upload: one empty page with only the demo footer.
            story.append(Spacer(1, 180 * mm))
            story.append(Paragraph("(blank page)", footer_style))
        if key == "faculty_list":
            table = Table(
                [
                    ["Name", "Designation", "Department"],
                    ["Fictional Faculty A", "Professor", "Computer Science"],
                    ["Fictional Faculty B", "Associate Professor", "Civil Engineering"],
                    ["Fictional Faculty C", "Assistant Professor", "Management"],
                ]
            )
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ]
                )
            )
            story.extend([Spacer(1, 4 * mm), table])
        document = SimpleDocTemplate(
            str(target),
            pagesize=A4,
            title=title,
            author="AICTE demo seed",
            subject="Fictional demo document",
        )
        document.build(story)
        logger.debug(" wrote demo document %s", target)

    logger.info(" demo PDFs ready in %s", root)
    return dict(_DOC_PATHS)
