"""re-cite the rule library against the handbook chapter it belongs to

Revision ID: 0017_rule_clause_citations
Revises: 0016_required_documents_coded
Create Date: 2026-10-27 12:40:00.000000

The first cut of the clause-cited rule library took three clause numbers from
the section headings of ``docs/reference/APH_SPEC.md`` instead of the handbook:

* faculty norms were cited as ``APH 7.1``, which is the penal-action
  introduction; the norms live in ``APH 6.14`` and Annexure-5;
* internet bandwidth, language-laboratory computers and the essential-requirement
  language laboratory were cited as ``APH 7.3``, which lists the penal actions;
  they are ``APH Annexure-4`` and ``APH 6.53(q)``;
* Affidavit 2 and the digital-signature rules were cited as ``APH 8``, which is
  the handbook's FAQ chapter; they are ``APH 6.39`` and ``APH 2.3.4a``.

The fire-safety rule additionally pointed at Annexure-2.1(iv), which is the
structural-stability certificate; the fire certificate is Annexure-2.1(v).

Fresh databases load the corrected ``seeds/aph/compliance_rules.json``. The
seed is insert-only, so existing installations need this migration to pick the
corrections up. Every statement matches the old value, so a clause an
administrator has already edited is left untouched.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_rule_clause_citations"
down_revision: str | None = "0016_required_documents_coded"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Declared as tables rather than raw SQL so the mixed-case ``apH_clause``
# identifier keeps its quotes on PostgreSQL.
_rules = sa.table(
    "compliance_rules",
    sa.column("code", sa.String),
    sa.column("apH_clause", sa.String),
    sa.column("penalty_codes", postgresql.JSONB),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
_faculty = sa.table(
    "faculty",
    sa.column("apH_clause", sa.String),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

_CLAUSES: tuple[tuple[str, str, str], ...] = (
    # code, old clause, corrected clause
    ("APH-FSR-UG-ET", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FSR-PG-ET", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FSR-DIPLOMA", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FSR-UG-PLANNING", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FSR-UG-MANAGEMENT", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FSR-PG-MANAGEMENT", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FSR-UG-MCA", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FSR-PG-MCA", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FAC-ESTABLISHMENT", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FAC-CADRE", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-FAC-HOD-DIPLOMA", "APH 7.1", "APH 6.14, Annexure-5"),
    ("APH-COMP-BANDWIDTH", "APH 7.3", "APH Annexure-4"),
    ("APH-COMP-LANG-LAB", "APH 7.3", "APH Annexure-4"),
    ("APH-ESS-LANGUAGE-LAB", "APH 7.3", "APH 6.53(q)"),
    ("APH-DOC-FIRE", "APH Annexure-2.1(iv)", "APH Annexure-2.1(v)"),
    ("APH-DOC-AFFIDAVIT2", "APH 8", "APH 6.39"),
    ("APH-DOC-AFFIDAVIT2-DSC", "APH 8", "APH 6.39"),
    ("APH-DOC-DSC", "APH 8", "APH 2.3.4a"),
)

_PENALTIES: tuple[tuple[str, list[str], list[str]], ...] = (
    # code, old codes, corrected codes
    ("APH-DOC-FIRE", ["7.4j"], ["7.4a"]),
    ("APH-DOC-STRUCTURAL", ["7.4j"], ["7.4a"]),
    ("APH-ADM-LOW-ENROLMENT", ["7.4g"], []),
)


def upgrade() -> None:
    bind = op.get_bind()
    for code, old_clause, new_clause in _CLAUSES:
        bind.execute(
            _rules.update()
            .where(_rules.c.code == code, _rules.c.apH_clause == old_clause)
            .values(apH_clause=new_clause, updated_at=sa.func.now())
        )

    for code, old_codes, new_codes in _PENALTIES:
        bind.execute(
            _rules.update()
            .where(
                _rules.c.code == code,
                _rules.c.penalty_codes == sa.cast(old_codes, postgresql.JSONB),
            )
            .values(penalty_codes=new_codes, updated_at=sa.func.now())
        )

    # Seeded faculty rosters recorded the same penal-chapter clause.
    bind.execute(
        _faculty.update()
        .where(_faculty.c.apH_clause == "APH 7.1")
        .values(apH_clause="APH 6.14", updated_at=sa.func.now())
    )


def downgrade() -> None:
    # The corrected citations are the accurate ones; restoring the mis-citations
    # would silently reintroduce an unverified claim about the handbook. The
    # downgrade therefore leaves the rows untouched.
    pass
