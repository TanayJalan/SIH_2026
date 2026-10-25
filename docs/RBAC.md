# Role-Based Access Control Matrix

> **APH reference:** APH_SPEC section 1 (Annexure-16, Definitions) and the Role mapping paragraph.
> Every row below is derived from the official committee compositions and the principle of
> least-privilege; nothing here is invented. Items marked ⚠ are ambiguous in the handbook and are
> tracked in `docs/OPEN_QUESTIONS.md`.

## Roles (ten system roles)

| Role constant | APH name | APH ref |
|---|---|---|
| `INSTITUTION_ADMIN` | Applicant / Institution | APH 1.8c |
| `REGULATION_BUREAU_OFFICER` | Regulation Bureau | APH 1.8a |
| `SCRUTINY_COMMITTEE_MEMBER` | Scrutiny / Re-Scrutiny Committee | APH 1.8a, 16.3–16.4 |
| `EVC_MEMBER` | Expert Visit Committee | APH 1.9a, 16.5 |
| `REGIONAL_OFFICER` | Regional Office / Regional Officer | APH Definitions 29 |
| `SHC_MEMBER` | Standing Hearing Committee | APH 16.6, 16.8 |
| `SAC_MEMBER` | Standing Appellate Committee | APH 16.6, 1.11 |
| `EXECUTIVE_COMMITTEE_MEMBER` | Executive Committee | APH 1.10a, 16.2 |
| `COMPLAINT_SCRUTINY_MEMBER` | Standing Complaint Scrutiny Committee (SCSC) | APH 16.7, 7.10 |
| `SUPER_ADMIN` | Council / AICTE Secretariat | APH 16.1 |

---

## Permission matrix

Legend: **R** = read · **W** = write · **–** = no access · **own** = own institution only
· **rgn** = own AICTE region only · **asgn** = assigned cases only

| Resource | INSTITUTION_ADMIN | REGULATION_BUREAU_OFFICER | SCRUTINY_COMMITTEE_MEMBER | EVC_MEMBER | REGIONAL_OFFICER | SHC_MEMBER | SAC_MEMBER | EXECUTIVE_COMMITTEE_MEMBER | COMPLAINT_SCRUTINY_MEMBER | SUPER_ADMIN |
|---|---|---|---|---|---|---|---|---|---|---|
| Applications – list | R(own) | R(rgn) | R(asgn+rgn) | R(asgn) | R(rgn) | R | R | R | R | R |
| Applications – detail | R(own) | R(rgn) | R(asgn+rgn) | R(asgn) | R(rgn) | R | R | R | R | R |
| Applications – create draft | W | – | – | – | – | – | – | – | – | W |
| Applications – submit | W(own) | – | – | – | – | – | – | – | – | W |
| Applications – assign officer | – | W(rgn) | – | – | W(rgn) | – | – | – | – | W |
| Applications – workflow transitions | W(own submit) | W(verify_docs, auto_assign) | W(start_scrutiny, raise_deficiency, close_deficiency) | W(submit_inspection_report) | W(schedule_inspection, send_to_committee) | W(SHC hearing actions) | W(SAC hearing actions) | W(approve, conditionally_approve, reject) | – | W |
| Institutions – list | R(own) | R(rgn) | R(rgn) | R(asgn) | R(rgn) | R | R | R | R | R |
| Institutions – detail | R(own) | R(rgn) | R(rgn) | R(asgn) | R(rgn) | R | R | R | R | R |
| Documents – list | R(own) | R | R | R | R | R | R | R | R | R |
| Documents – upload | W(own) | – | – | – | – | – | – | – | – | W |
| Documents – verify/flag | – | W | W | – | – | – | – | – | – | W |
| Deficiencies – raise | – | W | W | – | – | – | – | – | – | W |
| Deficiencies – respond | W(own) | – | – | – | – | – | – | – | – | W |
| Deficiencies – close | – | W | W | – | – | – | – | – | – | W |
| Inspections – schedule | – | – | – | – | W(rgn) | – | – | – | – | W |
| Inspections – report | – | – | – | W(asgn) | – | – | – | – | – | W |
| Committees – select (auto) | – | W | – | – | W(rgn EVC) | – | – | – | – | W |
| Committees – view members | R(own case) | R | R(asgn) | R(asgn) | R(rgn) | R | R | R | R | R |
| Compliance results – view | – | R | – | – | R(rgn) | – | – | – | – | R |
| Compliance rules – admin | – | – | – | – | – | – | – | – | – | W |
| Alert rules – admin | – | – | – | – | – | – | – | – | – | W |
| Alerts – own | R/Ack | R/Ack | R/Ack | R/Ack | R/Ack | R/Ack | R/Ack | R/Ack | R/Ack | R/Ack |
| Audit logs – list | – | R(rgn) | – | – | R(rgn) | – | – | – | – | R |
| Expert pool – view | – | R | R | R | R | R | R | R | R | R |
| Expert pool – manage | – | – | – | – | – | – | – | – | – | W |
| Complaints – file | W(own) | – | – | – | – | – | – | – | – | W |
| Complaints – view | R(own) | R | – | – | R(rgn) | R | R | R | R | R |
| Complaints – process (SCSC) | – | – | – | – | – | – | – | – | W | W |
| Appeals – file | W(own, within 7 days of LoD) | – | – | – | – | – | – | – | – | W |
| Appeals – view | R(own) | R | – | – | R(rgn) | R | R | R | R | R |
| Appeals – decide (SAC) | – | – | – | – | – | – | W | – | – | W |

---

## Institution scoping rule (APH_SPEC section 1)

`INSTITUTION_ADMIN` users **must only see data belonging to their own institution**.
This is enforced in:
- `app.services.authorization.application_scope`
- `app.services.authorization.institution_scope`
- `app.services.authorization.can_access_application`
- `app.services.committee.CommitteeService` (committee subject application must belong to user's institution or user must have panel-wide access)

---

## Committee composition rules (APH_SPEC section 1, Annexure-16)

These are stored as data in the `committee_compositions` DB table (admin-editable) and enforced
by `CommitteeService.select_committee()`. The table below documents the seed values.

| Committee | Seats (APH clause) | Quorum |
|---|---|---|
| Scrutiny Ch I (NEW_INSTITUTION) | 1 × Professor/Assoc. Prof (IIT/IIM/NIT/Govt) + 1 × Advocate (Bar Council) + 1 × Architect or Prof Civil/Structural | All (16.3) |
| Scrutiny Ch II (EXISTING / EoA) | 2 × Professor/Assoc. Prof (IIT/IIM/NIT/Govt) | All (16.4) |
| EVC | 1 × Academician ≥ Professor + 1 × Expert ≥ Assoc. Prof or industry ≥5 yr + 1 × Architect/CPWD/NBCC or Prof/Assoc.Prof Structural/Civil or Asst Prof Arch or Prof/Assoc.Prof Planning | All (16.5) |
| SHC | 1 × Chair (retired HC judge / VC / IIT/NIT/IIM Director) + 1 × Expert ≥ Assoc. Prof + 1 × Dy Director Revenue / Architect / Prof Civil / Prof Planning | All (16.6) |
| SAC | Same as SHC | All (16.6) |
| SCSC | 1 × Retired HC judge + 2 × Expert ≥ Assoc. Prof + 1 × Architect/Prof Civil + 1 × DTE/Registrar | Any 2 (16.7) |
| EC | Chairman + Vice-Chairman + Secretary MoE + others | 1/3 of members (16.2) |

Optional co-opt for Scrutiny/EVC/SHC/SAC: 1 State/UT/affiliating-university representative ≥ Assoc. Prof (APH 16 NOTE).

---

## Exclusion rules (enforced by `CommitteeService`)

1. **State-conflict**: no member from the same state as the applicant institution (APH 1.8a — automated portal selection).
2. **Consecutive-institution**: avoid assigning the same member to the same institution two cycles in a row (good practice, configurable).
3. **Load-balancing**: prefer members with the fewest recent assignments.
4. All selections store a `selection_seed` for reproducibility and auditing (APH 1.8a).
