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

* `DeadlineService` now starts the appeal and Security Deposit clocks and is used by
  `decision_letters` and the workflow guards. `applications.sla_due_at` is still
  computed from `sla_configs` by the workflow engine rather than by a `Timer` row, so
  SLA escalation and the statutory clocks remain two separate mechanisms.
* The APH fee calculator (`app/services/fee_calculator.py`) covers TER, the annual
  increase, the late penalty, extra committee charges, refund deductions and the Security
  Deposit, but the Security Deposit penalty windows are still calculator parameters rather
  than an admin-editable row (OQ-27).
* No admin UI yet for `application_type_routes`, `fee_schedules`, `security_deposit_schedules`,
  `public_notices`, `academic_calendar_events`, `committees` or `security_deposits`.
* Complaint and penal-action tables are modelled and seeded with reference data, but their
  end-to-end workflows are outside the one deep MVP flow. The appeal path (LoD/LoR →
  appeal window → SAC → Council → Regional endorsement) is implemented in Track A-D.

## 7. Workflow state machine

The workflow is seeded from `backend/seeds/aph/workflow_definitions.json`; see
`docs/WORKFLOW.md` for the rendered diagrams and the transition-to-clause table. The
following decisions are deliberately configuration or scope calls rather than handbook
facts.

| ID | Item | Status | Detail |
| --- | --- | --- | --- |
| OQ-29 | `LAST_DATE_EOA` for the demo year | CONFIGURABLE | The seeded `2026-27` calendar closes the EoA window on `2026-06-30`, which is already in the past for the system clock. Tests move the row forward. Replace the demo calendar with the real Public Notice before demonstrating an EoA decision. |
| OQ-30 | Random EVC sample | CONFIGURABLE | `workflow_definitions.config.random_evc_percent` is seeded at `10` (`TRACK_B`). APH 2.3.5a requires a random sample but does not publish a percentage. The sample is deterministic per application id so retries do not change the outcome. |
| OQ-31 | `council_ratification` reachability | OPEN | APH 2.25a describes Council ratification of an EC decision. In the normal Track A-D flow `ec_decide` already advances the status, so `council_ratification` is only reachable when a quorate EC `Decision` row exists while the application is still `EC_DECISION`; the integrity test seeds that state directly. Decide whether production should park a case at `EC_DECISION` for ratification or treat ratification as an out-of-band act. |
| OQ-32 | SHC hearing | CONFIGURABLE | The Standing Hearing Committee is modelled as a single `SHC_HEARING` state with a recorded outcome (APH 2.23.3), not as a multi-session hearing. Add sessions only if the Council publishes that process. |
| OQ-33 | Track C and Track D reuse | CONFIGURABLE | Tracks C and D reuse the Track A edges through `requires_scrutiny`, `requires_evc` and `requires_hearing`. Track B and Track C issue an EoA (`ACTIVE_EOA`); Track A issues an LoA and enters the Security Deposit cycle. The routing row, not the code, decides which flags apply. |
| OQ-34 | Track B Bureau verification | RESOLVED | Responded self-disclosure deficiencies need a verification step before the case can be cleared, so Track B has a `re_scrutiny_verify` self-loop on `SELF_DISCLOSURE_CHECK` (APH 1.8, 2.4). Without it, responded deficiencies could never close. |
| OQ-35 | `core_branches_required` | CONFIGURABLE | APH 2.6c requires Engineering & Technology to retain at least three core branches. The count lives in `workflow_definitions.config`; the keyword list used to identify branches is not seeded, so the guard passes until an administrator supplies `core_branch_keywords` or the application declares `data.core_branches`. |
| OQ-36 | Not-implemented application types | RESOLVED | `CLOSURE_AND_NEW_INSTITUTION`, `UNIVERSITY`, `MERGER_OF_INSTITUTIONS`, `EOA_AFTER_BREAK`, `DEEMED_UNIVERSITY_CONVERSION` and `ODL_ONLINE` are seeded with `not_implemented = true` and a note. The workflow raises HTTP 503 rather than inventing a path. |
| OQ-37 | Statutory-clock warning windows | CONFIGURABLE | The appeal-window warning fires at T-3 and the Security Deposit warnings at T-7 and T-1. APH fixes the seven-day appeal window (1.11a) and the fifteen-day deposit window (2.25f) but not the reminder points, so they live in `alert_rules.days_before` as editable rows with `needs_verification = true`. `complete_timers()` closes the corresponding `Timer` when the appeal is filed or the deposit is paid. |

## 8. Compliance engine: APH calculators and rule library

The rule library is data (`backend/seeds/aph/compliance_rules.json`), the calculator norms
are data (`backend/seeds/aph/compliance_config.json`), and the formulas are pure functions in
`app/services/compliance_calculators.py`. The rows below record where the handbook is silent,
ambiguous or contradicts another clause, so a reviewer can confirm the reading instead of
treating it as an AICTE fact.

| ID | Item | Status | Detail |
| --- | --- | --- | --- |
| OQ-38 | Cadre rounding for a non-multiple of nine | CONFIGURABLE | APH 6.14 and Annexure-5 fix the 1:2:6 ratio but not how to round a post count that is not a multiple of nine. The calculator rounds Professors and Associate Professors down and gives the remainder to Assistant Professors, so the total always equals the establishment (12 → 1/2/9, 8 → 1/1/6). A non-empty establishment always keeps at least one Professor because APH 6.14f requires one per programme. Confirm the Council's rounding convention. |
| OQ-39 | Principal/Director counted inside S/ratio | CONFIGURABLE | The Principal/Director is treated as the first Professor slot funded by S/ratio (APH 6.14, Annexure-5), not as an extra post on top of the establishment. Diploma counts the Principal inside S/25 and adds one HoD per department. If the Council intends an additional Principal post, `faculty_requirement` must add one. |
| OQ-40 | Meaning of “S” in S/ratio | OPEN | The calculator treats S as the sanctioned intake summed across every year of the programme (60 × 4 = 240 for a four-year B.Tech), which is the reading used in the seed data. APH_SPEC 7.1 does not spell out whether S is the annual intake or the total sanctioned strength. This choice changes the requirement by a factor of the programme duration, so it needs confirmation before the demo numbers are presented as handbook figures. |
| OQ-41 | Adjunct / Professor of Practice caps | CONFIGURABLE | APH 6.14d allows up to 15% adjunct faculty (20% for Design, 30% for Planning) and requires at least 10% Professors of Practice. The percentages live in `compliance_calculators.adjunct_cap` and are not yet an admin-editable `compliance_config` row; move them into the config table if the Council revises them. |
| OQ-42 | Instructional-area formula constants | CONFIGURABLE | Annexure-3 3.2 gives the room formula but the constants are hard-coded defaults in the calculator and can be overridden through `area_norms` (classroom 66 sqm for a 60-seat division, 33 sqm for 30 seats, tutorials at 25% of classrooms, one workshop at 200 sqm, plus CAD hall, computer centre, seminar hall, library and language lab). Confirm each constant against the current handbook/printer-friendly Annexure-3. |
| OQ-43 | Advisory rules that are deliberately not mandatory | CONFIGURABLE | Four real-clause rules are `mandatory = false` so they cannot block Nil Deficiency: `APH-LAND-LEASE-30` and `APH-LAND-LEASE-LIVE` (owned land has no lease term; the combined tenure rule is mandatory), `APH-AREA-CIRCULATION` (the built-up total already includes the 25% circulation factor), and `APH-LIB-NDL` (NDL membership is “desirable” under APH 6.54). `tests/test_compliance_rules.py` pins this list so an accidental advisory flag fails the build. |
| OQ-44 | Structural stability certificate trigger | CONFIGURABLE | APH 6.17h requires a structural stability certificate for buildings older than 30 years. The rule reads `infra_profile.building_completion_year` and a derived `document.structural.ok` metric, so a newer building is not penalised for a missing certificate. Buildings with no completion year are treated as not assessed (not failed). Confirm the 30-year threshold and the five-year validity period. |
| OQ-45 | Occupancy certificate cross-reference | OPEN | `required_documents` cites “APH Annexure-2.1(iii)” for the occupancy certificate, and APH_SPEC records that cross-reference pointing at a clause (“7.17”) that is not in the extract (see OQ-12). The document row stays `needs_verification = true` until the missing clause is found. |
| OQ-46 | `penalty_actions` configuration scope | CONFIGURABLE | `app/services/penal_actions.py` maps APH 7.4 a–n violations to APH 7.3 actions and only *suggests* them. A show-cause notice, hearing and speaking order remain mandatory workflow steps, and nothing in the compliance engine mutates an approval. The `penalty_actions` config row currently holds the `suggests_only`/`hearing_required` flags and the process steps; the violation-to-action map itself is code because it is a table of clause text, not a threshold. |
| OQ-47 | Legacy `DEMO-*` rules | RESOLVED | The earlier project-only thresholds are kept but seeded as `illustrative = true` and `mandatory = false`, and every screen shows an “Illustrative, not an AICTE norm” badge. Real rules are `mandatory = true` and cite an `APH` clause. An illustrative failure is reported as an advisory observation and never blocks a Nil Deficiency result. |
| OQ-48 | Bandwidth tiers | CONFIGURABLE | APH_SPEC 7.3 gives 100/300/500/1000 Mbps for intake up to 300/600/900/above 900. The tiers are `compliance_config.bandwidth_tiers` rows with a nullable catch-all top tier, so a revised table needs only a config edit. |
| OQ-49 | Library and computing norms | CONFIGURABLE | Titles, volumes, journals, reading seats, digital-library PCs, students-per-computer ratios, printer share and the 20-PC floor are calculator constants exposed through `library_norms`/`pc_ratios`. They are seeded from APH_SPEC 7.3/Annexure-4 and must be re-verified when the next handbook is published. |
| OQ-50 | Scoped metrics and missing programmes | RESOLVED | A family/level-scoped metric with no matching programme group returns “data missing” rather than the institution-wide value, so a rule written for a programme the institution does not run is unassessed instead of silently passing on an unrelated number. |
| OQ-51 | Clause citation audit | RESOLVED | The first rule-library draft took three clause numbers from the section headings of `APH_SPEC.md` instead of the handbook: faculty rules cited `APH 7.1` (the penal-action introduction; the norms are `APH 6.14`/Annexure-5), bandwidth and language-laboratory rules cited `APH 7.3` (the penal-action list; they are `Annexure-4` and `6.53(q)`), and the Affidavit 2/DSC rules cited `APH 8` (the FAQ chapter; they are `6.39` and `2.3.4a`). The fire certificate also pointed at Annexure-2.1(iv), the structural-stability item; it is (v). Migration `0017_rule_clause_citations` corrects existing rows and a test fails the build if a rule cites `7.1`, `7.2` or `7.3`. |
| OQ-52 | `required_documents` clause for Affidavit 2 and the TER receipt | OPEN | `backend/seeds/aph/required_documents.json` cites `APH 8` for `AFFIDAVIT_2` and `TER_RECEIPT` across all 27 application types. Chapter VIII is the handbook's FAQ, not a document requirement. The type-appropriate citations are Annexure-1 for a new institution, Annexure-2.1(i) for an existing institution, and `APH 2.3.2` for TER charges. Not corrected here because the rows are per application type and the seed is insert-only, so the fix needs a per-type mapping plus a data migration. |
| OQ-53 | Replacement limit per document | CONFIGURABLE | APH 1.8f and 2.4 require the institution to be given a chance to comply, and Re-Scrutiny verifies only the listed deficiencies (1.8g), but the handbook sets no cap on how many times one document may be replaced. The project applies `settings.max_reuploads_per_document` (default `5`, `MAX_REUPLOADS_PER_DOCUMENT` in `.env`) so a case cannot loop indefinitely. When the limit is reached the institution is told to contact the Regulation Bureau. Confirm a cap, or set it high enough to be effectively unlimited, before a real rollout. |

## 9. Document re-upload flow

Reviewer rejection and institution replacement are one flow: a Scrutiny Committee member
rejects a document with a reason code, the institution replaces exactly that file, and
Re-Scrutiny verifies only the replacement. The following are deliberate implementation
choices rather than handbook facts.

| ID | Item | Status | Detail |
| --- | --- | --- | --- |
| OQ-54 | Re-upload window | CONFIGURABLE | The institution may replace a `REJECTED`/`FLAGGED` document while the application is `DRAFT` (nothing is locked yet, APH 1.4.3), `DEFICIENCY_COMMUNICATED`, `INSTITUTION_COMPLIANCE`, `COMPLIANCE_WINDOW` (Track B self-disclosure) or `RE_SCRUTINY` (the 2.4 chance to comply). Every other state returns HTTP 409 with the clause. APH states the obligation but not a status vocabulary, so the window reads the seeded workflow states. |
| OQ-55 | Reason-code vocabulary | CONFIGURABLE | `DocumentRejectionReason` (`UNREADABLE`, `NO_DSC`, `EXPIRED`, `WRONG_DOCUMENT`, `NAME_MISMATCH`, `INCOMPLETE`, `OTHER`) is a fixed enum so the UI can show per-field guidance and the alerts can be templated. APH 1.8f lists no controlled vocabulary for deficiencies; extend the enum if the Council publishes one. |
| OQ-56 | Validity-date and DSC checks | CONFIGURABLE | A replacement upload must carry a DSC attestation with a signer name (APH 1.4.3, 1.4.6) and, for fire/occupancy/structural certificates, a `valid_until` date that is not already past (Annexure-2.1). The certificate families are matched by document type keyword in `document_verification.certificate_requires_validity`; add a family there if a new certificate type is introduced. The draft wizard stays lenient — it stores the signer, DSC flag and validity when supplied and blocks submission through the checklist (an unsigned document is marked `REJECTED`) — because APH 1.4.3 only locks the file at submission. The strict check runs on every replacement. |
| OQ-57 | PDF readability check | CONFIGURABLE | A PDF with no extractable text (blank or image-only scan) is blocked at upload because it cannot be verified. The check uses `pdfplumber` when installed and falls back to a printable-text heuristic, which is lenient by design so an unusual but valid PDF is not rejected. OCR (`pytesseract`) is optional and not required for the demo. |
| OQ-58 | Name-mismatch warning | CONFIGURABLE | When the institution name cannot be found in the extractable document text the upload is accepted with a warning, not blocked, because a certificate is often issued in another party's name (for example a bank or a chartered accountant). Reviewers see the warning and the reason codes let them reject with `NAME_MISMATCH`. |
