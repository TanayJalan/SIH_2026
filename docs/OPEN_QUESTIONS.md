# Open questions and verification register

This register tracks every place where the prototype had to make a domain decision that is not
fully settled by `docs/reference/APH_SPEC.md` (the authoritative extract of the APH 2024-27
handbook). Rows in the database that still need a handbook citation are marked
`needs_verification = true`; the build-failing test in
`backend/tests/test_aph_configuration.py` prevents new configuration rows from being added without
either a clause or that flag.

Status values: **OPEN** (needs a decision or handbook check), **CONFIGURABLE** (deliberately kept as
editable data), **RESOLVED** (decision recorded here).

## 1. Clause field spelling

| ID | Item | Status | Detail |
| --- | --- | --- | --- |
| OQ-01 | `apH_clause` column name | OPEN | `AGENTS.md` specifies the spelling `apH_clause`, so the code, database column and seed JSON use exactly that camel-case spelling (the column is quoted as `"apH_clause"` in raw SQL). It is very likely a typo for `aph_clause`. Renaming it later requires a schema migration plus a sweep of models, schemas, seeds, tests and the ER diagram. Confirm the intended spelling before the name is frozen by external consumers. |

## 2. Illustrative values that are not in the handbook

APH_SPEC §12.6 warns that dates in the PDF are examples tied to AY 2024-25. Cut-off dates,
committee dates and processing-time limits are not published in the handbook at all, so they live
in editable tables and are seeded with clearly labelled demo values.

| ID | Data | Status | Detail |
| --- | --- | --- | --- |
| OQ-02 | `public_notices` cut-off dates | CONFIGURABLE | Seeded `2026-27` Category 1 opens `2026-03-01` and closes `2026-04-30`; Category 2 opens `2026-03-01` and closes `2027-03-31`. All rows carry `is_demo = true` and `needs_verification = true`. Replace with the actual Public Notice for the live academic year. |
| OQ-03 | `academic_calendar_events` dates | CONFIGURABLE | Eight demo milestones are seeded (last date for EoA, enrolment upload, nomenclature concurrence, Security Deposit penalty windows, Internal Committee report, closure withdrawal, restoration). All carry `is_demo = true`. The `LAST_DATE_EOA` row is additionally `needs_verification = true` because the date is a policy decision, not a handbook date. |
| OQ-04 | `sla_configs` processing durations | CONFIGURABLE | Stage durations and escalation thresholds are demo values chosen for the prototype. They are not APH statutory periods and must be replaced by the Council's published processing calendar. Each row carries `apH_clause = 'DEMO'` and `needs_verification = true` so the configuration-coverage test keeps flagging it until a real citation or an explicit project-only decision is recorded. |
| OQ-05 | Legacy configuration rows | OPEN | Pre-existing `compliance_rules`, `alert_rules`, `required_documents` and `workflow_events` rows were backfilled with `apH_clause = 'DEMO'` and `needs_verification = true` rather than inventing citations. Each row needs a real clause or an explicit decision that it is a project-only rule. |

## 3. Application types and routing

| ID | Item | Status | Detail |
| --- | --- | --- | --- |
| OQ-06 | `CHANGE_IN_BANK_DETAILS` route | OPEN | The type is in APH Table 2.2, but the routing flags are derived from Annexure-2 clause 2.12, which is not a Table 2.3 row. The route is seeded `CAT2_YEAR_ROUND`, `needs_verification = true`. Confirm whether scrutiny, EVC or hearing applies. |
| OQ-07 | `DEEMED_UNIVERSITY_CONVERSION` route | OPEN | The type appears in Table 2.2, but APH_SPEC does not give a complete Table 2.3 routing row for it. It is seeded `CAT2_YEAR_ROUND`, `needs_verification = true`. Confirm the required steps. |
| OQ-08 | Table 2.3 self-disclosure dashes | OPEN | APH_SPEC §12.8 notes that Table 2.3 shows “–” under Self-Disclosure for types that other clauses require to have “Nil Deficiency based on Self-Disclosure”. The route table stores `requires_self_disclosure` and `nil_deficiency_required` as independent flags so the ambiguity can be resolved per type without a code change. |
| OQ-09 | Legacy application-type mapping | RESOLVED | `NEW` → `NEW_INSTITUTION`, `EXTENSION` → `EOA_SELF_DISCLOSURE`, `INTAKE_CHANGE` → `INCREASE_INTAKE`. The mapping preserves every existing row; `0009_aph_data` performs it in both directions. |

## 4. APH_SPEC §12 ambiguities

| ID | APH_SPEC §12 item | Status | Implementation decision |
| --- | --- | --- | --- |
| OQ-10 | Core-branch reduction: 2.6g allows up to 50% (not below 30 seats); 2.18a says up to 30 seats. | CONFIGURABLE | No hard-coded limit. The limit belongs in a compliance/fee parameter row so both readings can be configured. |
| OQ-11 | Appeal clock: 1.11a counts 7 days from issue of the LoD; 2.24a counts 7 days from uploading the decision. | CONFIGURABLE | `deadline_rules.APPEAL_WINDOW` seeds `start_event = DECISION_UPLOADED` (2.24a) with `start_event_configurable = true`; an administrator can switch it to a LoD-issue event. `DeadlineService` resolves the event and creates a `Timer`. `applications.appeal_deadline` remains the application read-model field. |
| OQ-12 | Cross-references to missing clauses: Annexure-2.1(iii) cites “7.17”; Annexure-3 3.2f cites “Chapter VII”; 2.18b cites Annexure 6/7; 2.13.1 cites “2.10.2(b)” which does not exist. | OPEN | Clause text is stored as data. Do not invent the missing clause. Rows relying on an unresolved reference are `needs_verification = true`. |
| OQ-13 | Security Deposit term: text says 10 years; Affidavit 6 says “8 years/10 years”. | CONFIGURABLE | `security_deposits.maturity_on` is stored explicitly, so either term can be applied without a code change. Confirm the term to use for the demo. |
| OQ-14 | Table 1.3 divisions for E&T shows “6/12”. | CONFIGURABLE | `programmes.divisions` is an integer; the interpretation (6 × 60-seat or 12 × 30-seat divisions) is a seeding decision, not a constraint. |
| OQ-15 | Course lists contain duplicates and spelling variants. | RESOLVED | Names are normalised during seeding; duplicates are not inserted into `programmes` or `application_type_routes`. |
| OQ-16 | PG cadre ratio: R = 3 for PG E&T/HMCT, R = 9 for MCA/MBA/PGDM; PG Planning, Applied Arts and Design unmarked. | CONFIGURABLE | The ratio belongs in compliance configuration keyed by programme family and level; it is not hard-coded. |
| OQ-17 | Scrutiny for Chapter I is described as presenting originals, while online mode is the norm and recordings are made “for transparency”. | OPEN | `committees.mode` and `applications.evc_mode` record `ONLINE`, `PHYSICAL` or `HYBRID`. The operating rule for Chapter I scrutiny remains a process decision. |

## 5. Schema decisions that extend the original task specification

| ID | Item | Status | Detail |
| --- | --- | --- | --- |
| OQ-18 | `required_documents.apH_clause` / `needs_verification` | RESOLVED | The retrofit brief only named `doc_code` and `condition_expr`, but the project policy requires every document requirement to carry a clause. Both fields were added; legacy rows are `DEMO`/`true`. |
| OQ-19 | `RequiredDocument.doc_code` and `Document.doc_code` | RESOLVED | `documents.doc_code` is backfilled from `doc_type` so legacy uploads can be matched to the APH checklist. New uploads set it from the selected requirement. |
| OQ-20 | `institutions.pid` uniqueness | OPEN | `pid` is treated as the AICTE Permanent Institute ID and is unique. If the PID is only unique within a region or academic year, the constraint must be relaxed. |
| OQ-21 | Legacy `institutions.region` fallback | RESOLVED | Unknown legacy regions map to `WESTERN` during backfill so no row is lost; `region` remains for existing scoping, while new logic reads `aicte_region`. Verify the fallback against the real region master before production use. |
| OQ-22 | `applications.decision` naming | RESOLVED | The legacy model exposed a Python property `decision` returning the demo payload's decision. The APH column is mapped as `Application.decision_type` to the database column `"decision"`. API consumers see `decision_type`. |
| OQ-23 | Committee compositions | CONFIGURABLE | Compositions from APH_SPEC §1 are seeded into `compliance_config` under the key `committee_compositions`, not hard-coded in the committee service. Administrators can edit them. |
| OQ-24 | `SHOW_CAUSE_REPLY` duration | OPEN | APH 2.23.3 describes the show-cause step in the complaint/SHC path but does not state a reply period. The seed uses 15 days with `needs_verification = true` and `start_event_configurable = true`; replace the duration when the Council publishes one. |
| OQ-25 | `AlertTriggerCatalogue.SLA_BREACHED` | CONFIGURABLE | Processing-time limits are not published in the handbook, so this catalogue row uses `apH_clause = 'DEMO'` and `needs_verification = true`, matching the `sla_configs` decision in OQ-04. The other seven trigger rows cite the APH event they represent. |
| OQ-26 | Fixed-date deadline encoding | RESOLVED | `ENROLMENT_UPLOAD`, `IC_REPORT` and `CLOSURE_REVOKE` use the matching `CalendarEventKey` as `start_event` and `duration_days = 0`. The actual date remains in `academic_calendar_events` (OQ-03), so no handbook date is duplicated in code. |
| OQ-27 | Security Deposit penalty clock | CONFIGURABLE | APH 2.25f gives 15 days, then 10% up to 31 May and 20% up to 31 July. The dates are parameters of the pure `security_deposit_penalty` calculator (`SecurityDepositPenaltyWindows`) so they can change without touching the arithmetic, but they are not yet a DB-backed admin row. The 10%/20% rates themselves are fixed by the clause. |
| OQ-28 | Security Deposit rate table | CONFIGURABLE | Table 1.4 base amounts are seeded into `security_deposit_schedules` (in paise) with double for leased premises. They are data, not code, so a revised table only needs re-seeding; the leased doubling is also stored per row. |

## 6. Related implementation gaps (not domain ambiguities)

These are known gaps in the prototype that this database/RBAC retrofit deliberately did not close.
They are listed so the next task does not mistake seeded data for working behaviour.

* `DeadlineService` exists for the new `DeadlineRule`/`Timer` tables, but the legacy
  `applications.sla_due_at` and `applications.appeal_deadline` calculations are not yet routed
  through it.
* The APH fee calculator (`app/services/fee_calculator.py`) covers TER, the annual
  increase, the late penalty, extra committee charges, refund deductions and the Security
  Deposit, but the Security Deposit penalty windows are still calculator parameters rather
  than an admin-editable row (OQ-27).
* No admin UI yet for `application_type_routes`, `fee_schedules`, `security_deposit_schedules`,
  `public_notices`, `academic_calendar_events`, `committees` or `security_deposits`.
* Complaint, appeal, penal-action and committee tables are modelled and seeded with reference data,
  but their end-to-end workflows are outside the one deep MVP flow.
