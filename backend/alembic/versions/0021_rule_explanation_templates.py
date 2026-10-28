"""give every real compliance rule a clause-quoting explanation

Revision ID: 0021_rule_explanation_templates
Revises: 0020_rule_scope_fixes
Create Date: 2026-10-28 05:30:00.000000

APH_SPEC section 11 requires every eligibility or compliance decision to return
an explanation. The engine already renders ``{observed}``, ``{threshold}``,
``{unit}``, ``{clause}`` and ``{result}``, but 62 of the real rules shipped
without a template, so a reviewer saw a generic fallback message that did not
quote the clause the rule enforces.

The seed is insert-only, so existing databases keep the old rows. This
migration fills in the missing templates in place; the rule library in
``backend/seeds/aph/compliance_rules.json`` is the source of truth.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021_rule_explanation_templates"
down_revision: str | None = "0020_rule_scope_fixes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEMPLATES: dict[str, str] = {
    'APH-FSR-UG-ET': (
        'UG Engineering & Technology faculty:student ratio is {observed} {unit}; '
        '{clause} requires at most {threshold}.'
    ),
    'APH-FSR-PG-ET': (
        'PG Engineering & Technology faculty:student ratio is {observed} {unit}; '
        '{clause} requires at most {threshold}.'
    ),
    'APH-FSR-DIPLOMA': (
        'Diploma faculty:student ratio is {observed} {unit}; {clause} requires at '
        'most {threshold}.'
    ),
    'APH-FSR-UG-PLANNING': (
        'UG Planning faculty:student ratio is {observed} {unit}; {clause} '
        'requires at most {threshold} (S divided by 16).'
    ),
    'APH-FSR-UG-MANAGEMENT': (
        'UG Management faculty:student ratio is {observed} {unit}; {clause} '
        'requires at most {threshold} (S divided by 25).'
    ),
    'APH-FSR-PG-MANAGEMENT': (
        'PG Management (MBA/PGDM) faculty:student ratio is {observed} {unit}; '
        '{clause} requires at most {threshold} (S divided by 20).'
    ),
    'APH-FSR-UG-MCA': (
        'UG Computer Applications (BCA) faculty:student ratio is {observed} '
        '{unit}; {clause} requires at most {threshold} (S divided by 25).'
    ),
    'APH-FSR-PG-MCA': (
        'MCA faculty:student ratio is {observed} {unit}; {clause} requires at '
        'most {threshold} (S divided by 20).'
    ),
    'APH-FSR-PG-PLANNING': (
        'PG Planning faculty:student ratio is {observed} {unit}; {clause} '
        'requires at most {threshold}.'
    ),
    'APH-FSR-UG-APPLIED-ARTS': (
        'UG Applied Arts & Crafts faculty:student ratio is {observed} {unit}; '
        '{clause} requires at most {threshold}.'
    ),
    'APH-FSR-PG-APPLIED-ARTS': (
        'PG Applied Arts & Crafts faculty:student ratio is {observed} {unit}; '
        '{clause} requires at most {threshold}.'
    ),
    'APH-FSR-UG-DESIGN': (
        'UG Design faculty:student ratio is {observed} {unit}; {clause} requires '
        'at most {threshold}.'
    ),
    'APH-FSR-PG-DESIGN': (
        'PG Design faculty:student ratio is {observed} {unit}; {clause} requires '
        'at most {threshold}.'
    ),
    'APH-FSR-UG-HMCT': (
        'UG HMCT faculty:student ratio is {observed} {unit}; {clause} requires at '
        'most {threshold}.'
    ),
    'APH-FSR-PG-HMCT': (
        'PG HMCT faculty:student ratio is {observed} {unit}; {clause} requires at '
        'most {threshold}.'
    ),
    'APH-FAC-ESTABLISHMENT': (
        'Appointed faculty is {observed} times the required establishment; '
        '{clause} requires at least {threshold}. Required posts are calculated as '
        'S divided by the sanctioned ratio.'
    ),
    'APH-FAC-CADRE': (
        'The appointed cadre mix is {result} with the 1:2:6 requirement in '
        '{clause}.'
    ),
    'APH-FAC-PRINCIPAL': (
        'A Principal/Director is required by {clause}; a vacancy beyond 12 months '
        'attracts penal action under APH 7.4b.'
    ),
    'APH-FAC-HOD-DIPLOMA': (
        'A Diploma institution needs one Head of Department per department '
        '({clause}): {result}.'
    ),
    'APH-FAC-PG-PHD': (
        'Every PG course needs a PhD-holding Professor, or a PhD Associate '
        'Professor when no qualified Professor is available ({clause}): {result}.'
    ),
    'APH-FAC-ADJUNCT-CAP': (
        'Adjunct and Professor-of-Practice posts above the permitted share: '
        '{observed} {unit}. {clause} allows 15% of required faculty, 20% for '
        'Design and 30% for Planning.'
    ),
    'APH-FAC-POP-MIN': (
        'Professor of Practice shortfall against the 10% minimum: {observed} '
        '{unit}. {clause} requires at least 10% of required faculty as Professors '
        'of Practice.'
    ),
    'APH-FAC-ECS': (
        '{observed} {unit} of faculty salaries are paid through ECS/RTGS/NEFT '
        'from a nationalised or scheduled commercial bank; {clause} requires '
        '{threshold} {unit}.'
    ),
    'APH-FAC-BIOMETRIC': (
        '{observed} {unit} of faculty attendance is captured biometrically; '
        '{clause} requires {threshold} {unit}.'
    ),
    'APH-FAC-ID-LAG': (
        'The longest lag between a joining or leaving date and the AICTE portal '
        'update is {observed} {unit}; {clause} requires the update in the same '
        'month, at most {threshold} {unit}.'
    ),
    'APH-FAC-REGULAR': (
        'Regular faculty share is {observed}%; {clause} requires regularly '
        'appointed faculty and permits contractual appointments only briefly in '
        'extraordinary cases. The {threshold}% minimum is a project assumption '
        'pending verification.'
    ),
    'APH-FAC-HEAD-VACANCY': (
        'The Principal/Director post has been vacant for {observed} {unit}; '
        '{clause} makes a vacancy beyond {threshold} months a violation.'
    ),
    'APH-LAND-TENURE': (
        'Land title or lease complies with {clause}: {result}.'
    ),
    'APH-LAND-PLOTS': (
        'The campus must comprise at most three plots, with the academic, '
        'instructional, administrative and amenity areas on one plot ({clause}): '
        '{result}.'
    ),
    'APH-LAND-DISTANCE': (
        'Every plot must lie within 2 km of the others, and hill and '
        'North-Eastern regions may use up to three pieces within 2 km ({clause}): '
        '{result}.'
    ),
    'APH-LAND-CONTIGUOUS': (
        'Land parcels must be contiguous ({clause}): {result}.'
    ),
    'APH-LAND-OBSTACLES': (
        'No river, canal, railway line, highway or high-tension line may cross '
        'the land ({clause}): {result}.'
    ),
    'APH-LAND-LEASE-30': (
        'Owned land needs no lease; leased land needs a registered lease of at '
        'least 30 years ({clause}): {result}.'
    ),
    'APH-LAND-LEASE-LIVE': (
        'The live lease must run at least as long as the longest course '
        '({clause}): {result}.'
    ),
    'APH-AREA-INSTRUCTIONAL': (
        'Instructional area available is short by {observed} {unit}; {clause} '
        'requires the full computed area.'
    ),
    'APH-AREA-BUILTUP': (
        'Built-up area falls {observed} {unit} short of the Annexure-3 '
        'requirement of instructional, administrative and amenities area plus '
        'about 25% access and circulation ({clause}).'
    ),
    'APH-AREA-ADMIN': (
        'Administrative area is {observed} times the 750 sq. m minimum for an '
        'intake up to 300 ({clause}): {result}.'
    ),
    'APH-AREA-AMENITIES': (
        'Amenities area is {observed} times the 500 sq. m minimum for an intake '
        'up to 300 ({clause}): {result}.'
    ),
    'APH-AREA-CIRCULATION': (
        'Access and circulation is {observed} {unit} of the instructional, '
        'administrative and amenities area; {clause} expects about {threshold} '
        '{unit}.'
    ),
    'APH-LIB-TITLES': (
        'Library titles fall {observed} {unit} short of the Annexure-4 '
        'requirement of 100 titles in the first year for E&T UG and 50 for '
        'Diploma, Management and Computer Applications, plus 50 per later year '
        '({clause}).'
    ),
    'APH-LIB-VOLUMES': (
        'Library volumes fall {observed} {unit} short of the Annexure-4 '
        'requirement of 5 x titles x divisions for UG and Diploma and 4 x titles '
        'x divisions for PG ({clause}).'
    ),
    'APH-LIB-JOURNALS': (
        'Subscribed indexed journals fall {observed} {unit} short of six per '
        'course per level for UG and PG programmes ({clause}).'
    ),
    'APH-LIB-SEATS': (
        'Reading-room seats fall {observed} {unit} short of 15% of students '
        '(maximum 150) for UG and Diploma and 25% (maximum 100) for PG '
        '({clause}).'
    ),
    'APH-LIB-NDL': (
        'National Digital Library membership is required by {clause}: {result}.'
    ),
    'APH-COMP-PCS': (
        'Computers fall {observed} {unit} short of the PC:student ratio, which '
        'carries a minimum of 20 computers ({clause}).'
    ),
    'APH-COMP-PRINTERS': (
        'Printers are {observed} {unit} of the installed computers; {clause} '
        'requires at least {threshold} {unit}.'
    ),
    'APH-COMP-BANDWIDTH': (
        'Internet bandwidth falls {observed} {unit} short of the tier for the '
        'sanctioned intake (100 Mbps up to 300, 300 Mbps for 301-600, 500 Mbps '
        'for 601-900 and 1 Gbps above 900) ({clause}).'
    ),
    'APH-COMP-LANG-LAB': (
        'Language-laboratory computers fall {observed} {unit} short of 20 per 300 '
        'intake pro rata ({clause}).'
    ),
    'APH-ESS-ANTIRAGGING': (
        'The Anti-Ragging Committee, squad and CCTV coverage are {observed} of '
        'the {threshold} required elements ({clause}).'
    ),
    'APH-ESS-IC': (
        'An Internal Committee with the prescribed composition is required '
        '({clause}): {result}.'
    ),
    'APH-ESS-IC-REPORT': (
        'The Internal Committee annual report must be uploaded on the portal by '
        '30 June ({clause}): {result}.'
    ),
    'APH-ESS-SCST': (
        'An SC/ST committee of five members, at least two SC/ST and at least one '
        'woman, is required ({clause}): {result}.'
    ),
    'APH-ESS-GRIEVANCE': (
        'Grievance redressal and the Ombudsperson are {observed} of the '
        '{threshold} required elements ({clause}).'
    ),
    'APH-ESS-IIC': (
        "An Institution's Innovation Council with its certificate and "
        'registration number is required ({clause}): {result}.'
    ),
    'APH-ESS-BARRIER-FREE': (
        'Barrier-free facilities as per CPWD and NBC are required ({clause}): '
        '{result}.'
    ),
    'APH-ESS-ABC': (
        'Academic Bank of Credits registration and compliance is mandatory '
        '({clause}): {result}.'
    ),
    'APH-ESS-CAMPUS-SAFETY': (
        'Campus safety and security arrangements are required ({clause}): '
        '{result}.'
    ),
    'APH-ESS-FOOD-SAFETY': (
        'Food Safety and Standards Act compliance for the canteen and mess is '
        'required ({clause}): {result}.'
    ),
    'APH-ESS-DIGITAL-PAYMENTS': (
        'All payments to and from students must be through digital modes '
        '({clause}): {result}.'
    ),
    'APH-ESS-LETTERS': (
        'LoA and EoA letters since inception and the accreditation status must be '
        'displayed on the institution website ({clause}): {result}.'
    ),
    'APH-ESS-MANDATORY-DISCLOSURE': (
        'The Annexure-18 mandatory disclosure must be published in full on the '
        'website and in the brochure ({clause}): {result}.'
    ),
    'APH-ESS-MENTAL-HEALTH': (
        'A mental-health counselling platform must be available to students '
        '({clause}): {result}.'
    ),
    'APH-ESS-WOMEN-HELPLINE': (
        'A 24x7 women helpline must be operational ({clause}): {result}.'
    ),
    'APH-ESS-FIRST-AID': (
        'First aid and medical facilities must be available on campus ({clause}): '
        '{result}.'
    ),
    'APH-ESS-POTABLE-WATER': (
        'Potable drinking water must be available on campus ({clause}): {result}.'
    ),
    'APH-ESS-WASTE': (
        'Waste management and green-campus practices must be in place ({clause}): '
        '{result}.'
    ),
    'APH-ESS-INSURANCE': (
        'Student safety insurance and a group accident policy for employees are '
        'required ({clause}): {result}.'
    ),
    'APH-ESS-SEL': (
        'A social and emotional learning mechanism must be in place ({clause}): '
        '{result}.'
    ),
    'APH-ESS-INTERNSHIP': (
        'A compulsory internship with a published Internship Policy is required '
        'for final-year students ({clause}): {result}.'
    ),
    'APH-ESS-SWAYAM': (
        'SWAYAM and MOOC electives must be offered, and up to 40% of courses may '
        'be delivered through them ({clause}): {result}.'
    ),
    'APH-ESS-SKILLING': (
        'Skilling credits must be offered to students ({clause}): {result}.'
    ),
    'APH-ESS-IIC-CELL': (
        'An industry-institution cell must be established ({clause}): {result}.'
    ),
    'APH-ESS-LANGUAGE-LAB': (
        'A language laboratory must be available ({clause}): {result}.'
    ),
    'APH-ESS-IQAC': (
        'An IQAC must be constituted with the prescribed affidavit ({clause}): '
        '{result}.'
    ),
    'APH-ADM-EXCESS': (
        'Admissions exceeded the permitted seats by {observed} {unit}; {clause} '
        'imposes a fine of five times the total course fee per excess admission.'
    ),
    'APH-ADM-ENROLMENT-UPLOAD': (
        'Student enrolment data must be uploaded on the portal before 30 November '
        '({clause}): {result}.'
    ),
    'APH-ADM-LOW-ENROLMENT': (
        'The lowest admission rate of the last five years is {observed} {unit}; '
        '{clause} treats a fall below {threshold} {unit} of the approved intake '
        'as the reduced-enrolment trigger.'
    ),
    'APH-DOC-AFFIDAVIT2': (
        'The portal-generated common Affidavit 2 with its 33 declarations must be '
        'uploaded with the application ({clause}): {result}.'
    ),
    'APH-DOC-AFFIDAVIT2-DSC': (
        'Affidavit 2 must carry a digital signature certificate ({clause}): '
        '{result}.'
    ),
    'APH-DOC-OCCUPANCY': (
        'Occupancy/Completion Certificate: {result}. {clause} requires a valid '
        'certificate (Annexure-2.1(iii) cross-refers to it).'
    ),
    'APH-DOC-FIRE': (
        'A valid Fire Safety Certificate must be uploaded with the application '
        '({clause}): {result}.'
    ),
    'APH-DOC-STRUCTURAL': (
        'A Structural Stability Certificate is required for buildings older than '
        '30 years and stays valid for five years ({clause}): {result}.'
    ),
    'APH-DOC-ANNEXURE21': (
        'Mandatory Annexure-2.1 documents missing from the application: '
        '{observed}. {clause} requires every mandatory document for the '
        'application type before the EoA is downloaded.'
    ),
    'APH-DOC-DSC': (
        'Uploads without a digital signature: {observed}. {clause} requires every '
        'document to be digitally signed.'
    ),
    'APH-DOC-EXPIRED': (
        'Certificates that are expired on the reference date: {observed}. '
        '{clause} treats an expired certificate as not uploaded.'
    ),
}


def upgrade() -> None:
    statement = sa.text(
        "UPDATE compliance_rules SET explanation_template = :template "
        "WHERE code = :code"
    )
    for code, template in TEMPLATES.items():
        op.execute(statement.bindparams(template=template, code=code))


def downgrade() -> None:
    # Earlier migrations already gave three rules a template; downgrading this
    # one must not take those away.
    preserved = {
        "APH-FAC-ADJUNCT-CAP": (
            "Adjunct and Professor-of-Practice posts above the permitted share: "
            "{observed} {unit}. {clause} allows 15% of required faculty, 20% for "
            "Design and 30% for Planning."
        ),
        "APH-LAND-LEASE-30": (
            "Owned land needs no lease; leased land needs a registered lease of "
            "at least 30 years ({clause}): {result}."
        ),
        "APH-LAND-LEASE-LIVE": (
            "The live lease must run at least as long as the longest course "
            "({clause}): {result}."
        ),
    }
    statement = sa.text(
        "UPDATE compliance_rules SET explanation_template = NULL WHERE code = :code"
    )
    for code in TEMPLATES:
        if code in preserved:
            continue
        op.execute(statement.bindparams(code=code))
    restore = sa.text(
        "UPDATE compliance_rules SET explanation_template = :template "
        "WHERE code = :code"
    )
    for code, template in preserved.items():
        op.execute(restore.bindparams(template=template, code=code))
