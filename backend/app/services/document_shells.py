"""Downloadable, portal-generated document shells.

The prototype cannot produce a legally executed affidavit. It generates a
clearly fictional, printable HTML shell that an institution can download, print
on the prescribed e-stamp paper and swear before the competent authority. The
wording is paraphrased from APH_SPEC section 8 and must be verified against the
current Affidavit 2 before a real filing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

from app.models.application import Application

AFFIDAVIT_2_DECLARATIONS: tuple[str, ...] = (
    "All information and documents submitted in this application are true, complete and correct.",
    "The institution is located at the approved location and no other location is used.",
    "A valid Occupancy or Completion Certificate is uploaded.",
    "A Structural Stability Certificate is uploaded where the building is older than 30 years.",
    "A valid Fire Safety Certificate is uploaded.",
    "No other institution is run from the same campus without full disclosure.",
    "A regular and qualified Principal or Director is appointed.",
    "Faculty are appointed in the prescribed cadre ratio.",
    "The faculty-student ratio meets the applicable APH norm.",
    "No original certificates of faculty or students are retained by the institution.",
    "No admission is made without AICTE approval.",
    "All fees are paid digitally through the AICTE portal.",
    "The institution provides the prescribed sports facilities.",
    "An Internal Quality Assurance Cell (IQAC) is constituted.",
    "The Anti-Ragging Committee, squad and cell are constituted with CCTV coverage.",
    "The Internal Committee (IC) for sexual harassment is constituted.",
    "The SC/ST Committee is constituted with the prescribed composition.",
    (
        "The Student Grievance Redressal Committee, faculty grievance cell and "
        "Ombudsperson are in place."
    ),
    "The Institution's Innovation Council is constituted and registered.",
    "The IC annual report is uploaded by 30 June.",
    "Labour-law and minimum-wage compliance is maintained.",
    "The mandatory disclosure is published on the website and in the brochure.",
    "The mandatory disclosure single PDF is linked in the portal attachments tab.",
    "The approved intake and programme details are correctly stated.",
    "The institution has not run any unapproved programme.",
    "The land is owned or held on a valid lease of at least 30 years where applicable.",
    "The building plan is architect-certified and approved by the competent authority.",
    "No undisclosed court case, charge sheet or ragging case is pending against the institution.",
    "All AICTE letters (LoA/EoA) since inception are displayed on the website.",
    "The institution complies with the Academic Bank of Credit requirements where applicable.",
    "The institution operates a functioning online grievance redressal mechanism.",
    "The details of all other institutions run by the same trust are disclosed.",
    "The institution will inform AICTE of any change in these declared facts before the cut-off.",
)
"""33 declarations summarised from APH_SPEC section 8 (Affidavit 2)."""

_SHELL_CODES = {
    "AFFIDAVIT_2": "Affidavit 2",
    "TER_RECEIPT": "TER payment receipt",
    "TRUST_RESOLUTION_FORMAT_3": "Trust resolution (Format 3)",
    "CERTIFICATE_1": "Certificate 1 - advocate",
    "CERTIFICATE_2": "Certificate 2 - architect",
    "CERTIFICATE_3": "Certificate 3 - bank manager",
}


@dataclass(frozen=True, slots=True)
class ShellDocument:
    """One printable document shell."""

    filename: str
    media_type: str
    content: str


def shell_codes() -> dict[str, str]:
    """Return the document codes that have a generated shell."""
    return dict(_SHELL_CODES)


def build_document_shell(
    application: Application,
    doc_code: str,
    *,
    generated_at: datetime | None = None,
) -> ShellDocument:
    """Build the printable shell for ``doc_code`` from the application data."""
    code = doc_code.strip().upper()
    if code not in _SHELL_CODES:
        raise KeyError(code)
    generated_at = generated_at or datetime.now()
    institution = application.institution
    institution_name = institution.name if institution else "Fictional Institute"
    address = _institution_address(application)
    data = application.data if isinstance(application.data, dict) else {}
    head_name = _head_name(data) or "Authorised Signatory"

    if code == "AFFIDAVIT_2":
        body = _affidavit_2(
            application,
            institution_name=institution_name,
            address=address,
            head_name=head_name,
        )
    elif code == "TRUST_RESOLUTION_FORMAT_3":
        body = _format_3(
            application,
            institution_name=institution_name,
            address=address,
            head_name=head_name,
        )
    else:
        body = _certificate(
            code,
            application,
            institution_name=institution_name,
            address=address,
            head_name=head_name,
        )

    title = _SHELL_CODES[code]
    html = _wrap(
        title=title,
        application=application,
        generated_at=generated_at,
        body=body,
    )
    filename = f"{code.lower()}-{application.portal_application_no or application.id}.html"
    return ShellDocument(filename=filename, media_type="text/html", content=html)


def _wrap(
    *,
    title: str,
    application: Application,
    generated_at: datetime,
    body: str,
) -> str:
    institution = application.institution
    institution_name = institution.name if institution else "Fictional Institute"
    meta = (
        f"Application {escape(application.portal_application_no or str(application.id))} · "
        f"Academic year {escape(application.academic_year)} · "
        f"Generated {generated_at.strftime('%d %B %Y, %H:%M')}"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{escape(title)} - {escape(institution_name)}</title>
<style>
  body {{ font-family: Georgia, serif; color: #1c1c1c; margin: 32px; line-height: 1.55; }}
  .page {{ max-width: 820px; margin: 0 auto; }}
  .stamp {{ border: 2px dashed #8a6d3b; padding: 14px 18px; background: #fffaf0;
           margin-bottom: 20px; }}
  .stamp strong {{ letter-spacing: 0.08em; }}
  h1 {{ font-size: 20px; text-align: center; text-transform: uppercase;
       letter-spacing: 0.06em; }}
  h2 {{ font-size: 15px; margin-top: 22px; }}
  .meta {{ font-size: 12px; color: #555; text-align: center; margin-top: -8px; }}
  ol {{ padding-left: 22px; }}
  li {{ margin-bottom: 7px; }}
  .signature {{ display: flex; justify-content: space-between; gap: 40px;
               margin-top: 46px; }}
  .signature div {{ flex: 1; border-top: 1px solid #333; padding-top: 8px;
                   font-size: 12px; }}
  .note {{ margin-top: 28px; font-size: 11px; color: #666;
          border-top: 1px solid #ccc; padding-top: 10px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 14px;
          font-size: 13px; }}
  td, th {{ border: 1px solid #bbb; padding: 8px; vertical-align: top; text-align: left; }}
  @media print {{ body {{ margin: 12mm; }} }}
</style>
</head>
<body>
<div class="page">
  <div class="stamp">
    <strong>₹100 e-STAMP (FICTIONAL DEMO)</strong><br />
    This is a prototype shell generated by the AICTE workflow demo. It is not a
    valid e-stamp and must not be filed. Swear the final affidavit on the
    prescribed e-stamp paper before a First Class Judicial Magistrate, Notary or
    Oath Commissioner (APH 1.4.5, 8).
  </div>
  <h1>{escape(title)}</h1>
  <p class="meta">{escape(meta)}</p>
  {body}
  <p class="note">
    Paraphrased from APH_SPEC section 8. The current AICTE Approval Process
    Handbook and the portal's Affidavit 2 wording prevail. All institutions,
    people and data in this document are fictional.
  </p>
</div>
</body>
</html>"""


def _affidavit_2(
    application: Application,
    *,
    institution_name: str,
    address: str,
    head_name: str,
) -> str:
    items = "\n".join(
        f"<li>{escape(declaration)}</li>" for declaration in AFFIDAVIT_2_DECLARATIONS
    )
    return f"""
<p>
  I, <strong>{escape(head_name)}</strong>, on behalf of
  <strong>{escape(institution_name)}</strong>, situated at {escape(address)},
  do hereby solemnly affirm and declare as follows in support of the application
  bearing number <strong>{escape(application.portal_application_no or str(application.id))}</strong>
  for the academic year <strong>{escape(application.academic_year)}</strong>:
</p>
<ol>
{items}
</ol>
<p>
  I declare that the above statements are true to the best of my knowledge and
  belief, and that no material fact has been concealed. I understand that
  furnishing false information invites penal action under APH 2.3.5b and 7.4a,
  including criminal proceedings against the Director/Principal and
  Chairman/Secretary.
</p>
<div class="signature">
  <div>Deponent: {escape(head_name)}<br />Signature and date</div>
  <div>Before: First Class Judicial Magistrate / Notary / Oath Commissioner<br />
  Signature, seal and date</div>
</div>
"""


def _format_3(
    application: Application,
    *,
    institution_name: str,
    address: str,
    head_name: str,
) -> str:
    return f"""
<p>
  Certified true copy of the resolution passed by the Trust / Society / Company
  running <strong>{escape(institution_name)}</strong>, {escape(address)}.
</p>
<p>
  The competent authority of the Trust / Society / Company, in its meeting held
  on ____________________, resolved as follows:
</p>
<ol>
  <li>
    To authorise <strong>{escape(head_name)}</strong> to sign, upload and submit
    the AICTE application bearing number
    <strong>{escape(application.portal_application_no or str(application.id))}</strong>
    for the academic year <strong>{escape(application.academic_year)}</strong>,
    including any reopening or representation under APH 2.3.3d-e.
  </li>
  <li>
    To affirm that the land, building, funds and faculty declared in the
    application are available and are not encumbered in a manner that defeats
    the approval.
  </li>
  <li>
    To authorise the payment of the prescribed TER, late penalty and any
    additional committee charges through the AICTE portal.
  </li>
  <li>
    To authorise the signatory to appear before the Scrutiny Committee, Expert
    Visit Committee, Standing Hearing Committee or Standing Appellate Committee
    as required.
  </li>
</ol>
<div class="signature">
  <div>Chairman / Authorised Signatory<br />Name, signature and seal</div>
  <div>Trust / Society / Company Secretary<br />Name, signature and seal</div>
</div>
"""


def _certificate(
    code: str,
    application: Application,
    *,
    institution_name: str,
    address: str,
    head_name: str,
) -> str:
    details = {
        "CERTIFICATE_1": (
            "Certificate 1 - Advocate",
            "I have verified the documents uploaded with this application and find the "
            "Occupancy Certificate and Structural Stability Certificate to be authentic.",
            "Advocate enrolment number",
        ),
        "CERTIFICATE_2": (
            "Certificate 2 - Architect",
            "The site plan and building plans uploaded with this application are authentic "
            "and have been prepared by me or under my supervision.",
            "Architect registration number",
        ),
        "CERTIFICATE_3": (
            "Certificate 3 - Bank Manager",
            "The bank statement, fixed deposit receipt and fund-position evidence uploaded "
            "with this application are authentic, and the FDR is not pledged or mortgaged.",
            "Bank branch, officer name and code",
        ),
    }
    title, statement, credential = details[code]
    return f"""
<h2>{escape(title)}</h2>
<p>
  I, <strong>{escape(head_name)}</strong>, certify in relation to
  <strong>{escape(institution_name)}</strong>, {escape(address)}, and the AICTE
  application bearing number
  <strong>{escape(application.portal_application_no or str(application.id))}</strong>
  for the academic year <strong>{escape(application.academic_year)}</strong> that:
</p>
<p>{escape(statement)}</p>
<table>
  <tr><th>{escape(credential)}</th><td></td></tr>
  <tr><th>Name</th><td></td></tr>
  <tr><th>Signature</th><td></td></tr>
  <tr><th>Date and seal</th><td></td></tr>
</table>
"""


def _institution_address(application: Application) -> str:
    institution = application.institution
    if institution is None:
        return "Fictional Campus, Demo Nagar"
    return f"{institution.name}, {institution.state}"


def _head_name(data: dict[str, object]) -> str | None:
    profile = data.get("institution_profile")
    if not isinstance(profile, dict):
        return None
    value = profile.get("head_name")
    return value if isinstance(value, str) and value.strip() else None
