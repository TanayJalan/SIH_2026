# APH 2024-27 Gap Report

**Audit date:** 24 October 2026  
**Repository:** `SIH2.0`  
**Authoritative source:** [`docs/reference/APH_SPEC.md`](reference/APH_SPEC.md), the supplied extract of the *AICTE Approval Process Handbook 2024-25 to 2026-27*  
**Code baseline:** backend migrations `0001`-`0007`, the FastAPI application, the React frontend, and the seed data as they exist in this repository.  
**Constraint:** this step is documentation-only. No backend, frontend, migration, seed, or test file was modified.

---

## 0. Executive summary

The prototype is a solid **generic approval workflow** with a strong audit trail, configurable compliance rules, a configurable alert engine, versioned document uploads, and useful role scoping. It is **not yet an APH-compliant approval system**.

The largest structural gaps are:

1. **Roles and committees.** The system has five roles. APH §1 defines ten system roles, including Regulation Bureau, Scrutiny Committee, EVC, SHC, SAC, Executive Committee and SCSC. The current `SCRUTINY_OFFICER`, `INSPECTION_COMMITTEE` and `REGIONAL_HEAD` roles combine duties that APH separates. `REGIONAL_HEAD` currently exercises decision powers that belong to the Executive Committee and Council.
2. **Workflow.** The current linear flow (`DRAFT → SUBMITTED → DOCUMENT_VERIFICATION → SCRUTINY → DEFICIENCY → INSPECTION → COMMITTEE_REVIEW → APPROVED/REJECTED`) is not the Annexure-7 flow. Re-Scrutiny, SHC, EC, Council ratification, LoA/LoD/LoR, appeal/SAC, and the Security Deposit step are absent.
3. **Application coverage.** The portal can create only `NEW` and `EXTENSION` applications. APH §2's Table 2.3 alone has 21 rows, and the category lists add off-campus and extended-EoA tracks plus Chapter I and university variants. The data model cannot express most of them.
4. **Money and statutory clocks.** There is no TER/fee calculator, payment gate, refund engine, or Security Deposit lifecycle. APH says unpaid applications are not considered (1.4.2e-f), requires a 15-day deposit clock with 10%/20% penalties (2.25f), and gives a 7-day appeal window (1.11a, 2.24a).
5. **Compliance substance.** The 15 seeded compliance rules are illustrative generic thresholds, not APH formulas. The system does not compute faculty requirement from approved intake, built-up area, library volumes, PCs, bandwidth, cadre ratio, or the 6.47-6.53 essential-requirements checklist.
6. **Alerts.** The eight alert triggers cover generic SLAs and document expiry. They do not model APH statutory events, committee hearings, EC/Council decisions, appeals, deposits, enrolment deadlines, or complaint-report deadlines.
7. **UI.** The shell has five role-specific navigations. The case file has a seven-stage track and six tabs. There are no SHC/SAC/EC/SCSC queues, hearing panels, letter viewer, appeal timer, or Security Deposit panel.

**Bottom line for a four-day deadline:** the repository is a good demo of *workflow mechanics*, not yet a credible demo of the *AICTE approval process*. The highest-value four-day slice is to make roles, the core workflow, decision letters, payment gates, and the case-file vocabulary APH-shaped. The full APH compliance calculator and committee engine cannot be completed honestly in four days; they should be staged as a visible roadmap rather than faked.

### Effort scale

| Size | Meaning in this report |
|---|---|
| **S** | Under 30 minutes: rename, add a field, add a guard, adjust copy, or add a small test. |
| **M** | 30 minutes to one working day: a focused endpoint/service change, a migration plus tests, or a contained UI panel. |
| **L** | More than one working day: a new domain model, a multi-step workflow branch, a calculator engine, or a cross-cutting UI/API change. |

Effort is an implementation estimate for this codebase, not a statement that the whole APH scope is feasible by the deadline.

---

## 1. Database schema

### 1.1 Existing tables

The live schema is created by `backend/alembic/versions/0001_initial_schema.py` through `0007_alert_recipient_cascade.py`. ORM models live in `backend/app/models/`.

| Table | What it stores today | APH fit |
|---|---|---|
| `institutions` | Name, demo AICTE ID, state, region, type, established year, NAAC/NBA strings. | Too thin for Annexure-1/2 identity, promoter/trust, campus, land, affiliation, minority/government status. |
| `users` | Name, email, password hash, one role, optional institution, optional region, active flag. | No committee membership, authorised-representative record, conflict-of-interest declaration, or DSC identity. |
| `applications` | Institution, application type, academic year, status, current stage, assignee, SLA dates, withdrawal/escalation flags, risk/compliance scores, JSONB `data`. | Generic case record; status and type vocabularies are not APH; JSONB hides the data needed for APH calculations and evidence. |
| `application_programs` | Programme name, level, intake, faculty count, lab count. | Cannot express divisions, shifts, course codes, existing approved intake, requested intake change, affiliation, NBA status, or the approved-intake ledger. |
| `documents` | Application, doc type, filename, MIME type, size, storage path, uploader, verification status/notes, expiry date, version. | Useful versioned upload primitive; no DSC/e-sign, affidavit/e-stamp metadata, issuer, Annexure mapping, generated letter, or acceptance/rejection certificate. |
| `required_documents` | Application type, doc type, mandatory flag. | Only seven generic document types; not the Annexure-1/2 matrix or the Table 2.3 per-type requirements. |
| `deficiencies` | Application, category, description, raiser, status, due date, response text/document, timestamps. | Single ad-hoc deficiency; no Deficiency Report, scrutiny round, observation type, Re-Scrutiny linkage, or SHC/EVC deficiency. |
| `inspections` | Application, one `committee_id`, scheduled date, status, JSONB report, recommendation. | Models one visitor, not an EVC team with composition, quorum, conflict checks, visit mode, checklist, video/GPS evidence, or SHC review. |
| `workflow_events` | Application, from/to status, actor, action, comment, JSONB details. | Good immutable transition log; constrained by the non-APH status/action vocabulary. |
| `audit_logs` | Actor, action, entity type/id, before/after JSONB, IP, timestamp. | Meets the project's who/what/when/before/after/IP requirement. Needs coverage for new committee, payment, letter and appeal writes. |
| `sla_configs` | One duration and escalation role per workflow stage. | Generic stage SLAs, not the APH statutory deadline calendar (appeal, deposit, enrolment, complaints, etc.). |
| `compliance_rules` | Code, name, category, description, metric key, operator, threshold(s), severity, applies-to string, active flag. | A good configurable rule primitive; no APH formula, clause reference, programme/level applicability, or evidence requirement. |
| `compliance_results` | Application, institution, rule, observed value, status, message, passed, evaluated-at. | Point-in-time result, but no captured inputs, formula version, evidence links, or reviewer override. |
| `compliance_config` | JSONB severity weights and RAG breakpoints. | Useful scoring configuration; RAG is a project invention, not an APH status. |
| `compliance_snapshots` | Institution-level score, health, failure counts, trigger, evaluated-at. | Trend chart only; no academic year, application type, approved intake, or post-approval monitoring context. |
| `alert_rules` | Code, name, description, hard-coded trigger type, days before, severity, channels, template, escalation role, active flag. | Configurable templates, but the trigger vocabulary is a database `CHECK`, so new statutory events require code and migration. |
| `alerts` | Recipient, application, rule, parent, type, severity, title, message, channel, status, sent/ack timestamps, escalation level, dedupe key. | Good delivery/dedupe primitive; no committee/role queue, hearing notice, decision letter, or EC/Council escalation semantics. |

### 1.2 Schema contradictions and gaps

| ID | Current schema | Why it is a problem / APH contradiction | APH reference | Effort |
|---|---|---|---|---|
| DB-01 | `ApplicationType` has only `NEW`, `EXTENSION`, `INTAKE_CHANGE`; the API accepts only `NEW`/`EXTENSION`. | APH has 21 application types in Tables 2.2/2.3 plus new-institution variants, university, ODL and collaboration tracks. Most cannot be represented. | §2, Tables 2.2/2.3; 1.3.2-1.3.3; Ch. III-V | L |
| DB-02 | `ApplicationStatus` has no Re-Scrutiny, EVC, SHC, EC, Council, LoA/LoD/LoR, appeal/SAC, deposit or complaint states. | The status enum hard-codes a linear private workflow instead of the Annexure-7/2.23 path. | §3.1-§3.5; 1.8-1.12; 2.23.3-2.24a | L |
| DB-03 | `CONDITIONALLY_APPROVED` is a terminal status and `conditionally_approve` is an action. | APH says no conditional approval normally and no partial approval. A conditional outcome is not a valid letter. | 4.9c; 2.27; 4.4.3 note | M |
| DB-04 | `institutions` lacks promoter/trust/society/company, registered address, campus/site, affiliation, government/aided/minority status, land parcels, lease and built-up-area inventory. | Annexure-1 requires these to establish eligibility and verify land/building; 1.3.4 restricts who may promote an institution. | 1.3.4; 1.5; 6.17; Annexure-1; Annexure-3 | L |
| DB-05 | `application_programs` stores only name/level/intake/faculty/lab count. | APH works in courses, levels, divisions, shifts, approved intake and year-wise intake; increase/new-programme/closure tracks need before/after values. | Table 1.3; 2.6; 2.7; 2.18; 6.13 | L |
| DB-06 | `applications.data` is an unversioned JSONB blob for profile, infrastructure, faculty, finance and accreditation. | APH compliance needs reproducible inputs and evidence. A mutable blob cannot prove what was assessed at scrutiny or EVC time. | §7; 6.53; Annexure-1/2 | L |
| DB-07 | `documents` has no digital-signature, affidavit, e-stamp, issuer, validity, Annexure-code or generated-letter fields. | APH requires DSC on every upload (no DSC = no submission), Affidavit 2, and a type-specific Annexure-1/2 document set. | 1.4.3; 1.4.5; §8; Annexure-1/2 | L |
| DB-08 | `required_documents` uses a fixed list per type: the same seven generic documents for both creatable types (`NEW`/`EXTENSION`), with no conditional rules. | Table 2.3 and Annexure-1/2 vary by application type; several types require Affidavit 8/9/10/11, NOCs, resolutions or additional certificates. | §2 Table 2.3; §8 | M |
| DB-09 | `deficiencies` is a flat list with one response and one closer. | APH requires a Deficiency Report (2.3.3b), a chance to comply before Scrutiny/Re-Scrutiny/SHC (2.4), and re-scrutiny of only listed deficiencies (1.8). | 2.3.3b; 2.4; 1.8; 2.23.3 | L |
| DB-10 | `inspections` has one `committee_id` and a free-form report. | EVC is a multi-member committee with prescribed composition, automated selection, conflict rules, quorum and an evidence checklist; deemed universities have a special chair. | 1.9a; Annexure-16 (16.5); 1.9f-g | L |
| DB-11 | `sla_configs` covers seven internal stages only. | APH deadlines are event-specific: 7-day appeal, 15-day deposit, 30 November enrolment, 30 June IC report, monthly complaint report, 12-month vacancy triggers. | §5; 1.11a; 2.24a; 2.25f/n; 6.48g; 7.13 | M |
| DB-12 | `compliance_rules.applies_to` is a free string and the seed uses `ALL`. | APH norms vary by programme, level, intake, government/private status and whether the institution is new or existing. | §7.1-§7.4; Annexure-5 | M |
| DB-13 | `compliance_results` stores only an observed number and message. | A result cannot be defended without the formula, input values, source documents, rule version and reviewer. | §7; 6.53; Annexure-18 | M |
| DB-14 | `alert_rules.trigger_type` is constrained by a hard-coded `CHECK` to eight values. | This violates the project rule that business rules are data: adding an APH deadline requires a migration and code change. | §5; §7.10; 7.13; project `AGENTS.md` rule 2 | M |
| DB-15 | `users` has one role and no committee/representative/COI tables. | APH separates applicant representatives, Regulation Bureau, Scrutiny, EVC, SHC, SAC, SCSC, EC and Council; members have compositions, quorums and conflicts. | §1; Annexure-16 (16.1-16.8); 1.8c; 1.11d; 2.24e | L |
| DB-16 | No payment, fee, refund, FDR or Security Deposit tables. | APH makes payment a precondition (1.4.2e-f), sets TER by type/category (Tables 1.1/2.1), and requires a 15-day deposit with penalties (2.25f). | §4; 1.12; 2.25f; 6.46 | L |
| DB-17 | No decision-letter, speaking-order, appeal, hearing, complaint or penal-action tables. | APH requires LoA/LoD/LoR with Speaking Order, a 7-day appeal to SAC, PGRC→SCSC→SHC→EC complaints, and penal-action hearings. | 1.10; 1.11; 2.24a; 7.10; §9 | L |
| DB-18 | No approved-intake ledger, enrolment or post-approval monitoring tables. | EoA is issued per academic year with Approved Intake; enrolment is uploaded before 30 November; monitoring and penalties depend on the ledger. | 2.25b/k/n; 6.12; 7.3-7.4 | L |

### 1.3 Missing schema (grouped)

| ID | Missing entity group | Minimum tables/fields needed | Effort |
|---|---|---|---|
| DB-M1 | Master data | `application_types`, `programmes`, `levels`, `regions`, `competent_authorities`, `document_types`, `affidavit_templates`, `academic_calendar` / `public_notice`; seed from APH §10. | L |
| DB-M2 | Applicant identity | `promoters`/`trusts`, `institution_campuses`, `institution_contacts`, `authorised_representatives`, `dsc_registrations`. | L |
| DB-M3 | Type-specific applications | `application_type_details`, `requested_courses`, `intake_changes`, `land_parcels`, `buildings`, `fee_structures`; before/after snapshots. | L |
| DB-M4 | Money | `fee_rules` (TER Table 1.1/2.1), `payments`, `refunds`, `security_deposits`, `fdr_records`, `penalties`. | L |
| DB-M5 | Committees | `committees`, `committee_members`, `committee_meetings`, `committee_assignments`, `conflict_declarations`, `quorum_records`; APH compositions in data. | L |
| DB-M6 | Scrutiny/EVC | `scrutiny_rounds`, `scrutiny_observations`, `deficiency_reports`, `evc_visits`, `evc_members`, `evc_checklists`, `evc_evidence` (video URL, GPS, photos). | L |
| DB-M7 | Decisions and appeals | `decisions`, `decision_letters` (LoA/LoD/LoR), `speaking_orders`, `council_ratifications`, `appeals`, `sac_hearings`, `appeal_timers`. | L |
| DB-M8 | Complaints/penalties | `complaints`, `pgrc_reviews`, `scsc_reviews`, `show_cause_notices`, `penal_actions`, `hearings`. | L |
| DB-M9 | Compliance evidence | `faculty_roster`, `infrastructure_rooms`, `lab_equipment`, `library_holdings`, `journals`, `computing_resources`, `essential_requirement_evidence`, `bog_members`, `mandatory_disclosure_snapshots`. | L |
| DB-M10 | Monitoring | `approved_intake_ledger`, `enrolment_uploads`, `institutional_compliance_cases`, `compliance_rule_versions`, `compliance_evidence_links`. | L |

### 1.4 Database verdict

The schema is **internally coherent but domain-thin**. The existing generic primitives (`applications`, `documents`, `workflow_events`, `audit_logs`, `compliance_rules`, `alerts`) are worth keeping. The APH work is mostly additive: master data, type-specific application detail, committees/hearings, money, decisions/appeals, and evidence. The dangerous shortcut is to keep forcing APH concepts into `ApplicationStatus` and the JSONB blob; that will produce a demo that cannot answer "which clause, which committee, which letter, which deadline?"

---

## 2. Roles and RBAC

### 2.1 Existing implementation

| Area | Files / symbols |
|---|---|
| Role vocabulary | `backend/app/models/enums.py` → `Role` |
| Tables | `users.role`, `users.institution_id`, `users.region`; `applications.assigned_officer_id`; `inspections.committee_id`; `alerts.recipient_user_id`; `audit_logs.actor_id` |
| Authentication | `backend/app/api/routes/auth.py`, `backend/app/core/security.py`, `backend/app/services/auth.py` |
| Route guards | `backend/app/api/dependencies.py` → `require_roles`, `CurrentUser` |
| Record scoping | `backend/app/services/authorization.py` → `application_scope`, `institution_scope`, `can_access_application`, `audit_log_scope` |
| Workflow permissions | `backend/app/services/workflow.py` → `Transition.roles`, `allowed_actions`, `perform_action` |
| Seed accounts | `backend/app/seed.py` → one demo account per role |
| Frontend labels/nav | `frontend/src/lib/roles.ts`, `frontend/src/components/RequireRoles.tsx`, `frontend/src/components/AppLayout.tsx` |

The five current roles are `INSTITUTION_ADMIN`, `SCRUTINY_OFFICER`, `INSPECTION_COMMITTEE`, `REGIONAL_HEAD` and `SUPER_ADMIN`. A user has exactly one role, an optional `institution_id` and an optional `region`. There is no role table, committee table or permission table; permissions are code in route decorators and the workflow transition table.

### 2.2 Current access map

| Surface | Who can use it | Scoping |
|---|---|---|
| `POST /auth/login`, `GET /auth/me` | Anyone with valid credentials | JWT, eight-hour expiry |
| `GET /applications`, `GET /applications/{id}`, `GET /applications/{id}/compliance` | All five roles | Institution, assignment/region, inspection assignment, or global |
| `/applications` draft, programme, document, checklist and submit endpoints | `INSTITUTION_ADMIN` only | Own institution only |
| `POST /applications/{id}/actions/{action}` | Any authenticated user, then filtered by `Transition.roles` | Institution/assignment/region |
| Timeline, deficiencies, inspections, committee members | All authenticated roles | Same application scope |
| `GET/POST/PATCH /compliance/*` | `SUPER_ADMIN`, `REGIONAL_HEAD` | Region for regional heads |
| `/alert-rules/*` | `SUPER_ADMIN` | Global |
| `/alerts/*` | Any authenticated user | Only alerts addressed to that user |
| `GET /audit-logs` | `SUPER_ADMIN`, `REGIONAL_HEAD` | Global or region |
| `GET /search` | Any authenticated user | Role-scoped results |
| `/dev/*` | Debug-mode development routes | Process-level demo clock |

### 2.3 Role contradictions and gaps

| ID | Current behaviour | Why it is a problem / APH contradiction | APH reference | Effort |
|---|---|---|---|---|
| RB-01 | Five roles: institution admin, scrutiny officer, inspection committee, regional head, super admin. | APH's system role map names ten roles: `INSTITUTION_ADMIN`, `REGULATION_BUREAU_OFFICER`, `SCRUTINY_COMMITTEE_MEMBER`, `EVC_MEMBER`, `REGIONAL_OFFICER`, `SHC_MEMBER`, `SAC_MEMBER`, `EXECUTIVE_COMMITTEE_MEMBER`, `COMPLAINT_SCRUTINY_MEMBER`, `SUPER_ADMIN`. | §1 role mapping; Annexure-16 | M |
| RB-02 | `SCRUTINY_OFFICER` verifies documents, raises/closes deficiencies and schedules inspections. | APH separates the Regulation Bureau (schedules committees, issues letters) from the Scrutiny/Re-Scrutiny Committee (verifies authenticity). A single officer role merges scheduling, adjudication and evidence verification. | 1.8a; 1.10; Annexure-16 (16.3-16.4) | L |
| RB-03 | `INSPECTION_COMMITTEE` is one user assigned via `inspections.committee_id`. | APH requires an Expert Visit Committee with prescribed multi-member composition, automated selection, conflict rules and a quorum. | 1.9a; Annexure-16 (16.5) | L |
| RB-04 | `REGIONAL_HEAD` can start scrutiny, send to committee, approve, conditionally approve and reject. | APH gives the approval decision to the Executive Committee, ratified by Council. The Regional Officer constitutes the EVC; the Regional Committee endorses LoA/LoR but does not replace EC. | 1.10a; §3.1 steps 6-8; Definitions 29; Annexure-7 | L |
| RB-05 | `SUPER_ADMIN` is included in every workflow transition and can perform every action. | APH separation of duties is the control that prevents one actor from scrutinising, inspecting, deciding and ratifying the same case. A superuser bypass destroys that control. | §1; 1.10a; Annexure-16 | M |
| RB-06 | No SHC, SAC, SCSC, EC or Council role. | These bodies are required for deficiencies, appeals, complaints, decisions and ratification. | §1; 2.23.3; 2.24a; 7.10; 1.10a | L |
| RB-07 | A `SCRUTINY_OFFICER` can read any application in their region, not only cases assigned to their committee. | Committee members should see assigned cases; regional visibility belongs to the Regulation Bureau/Regional Office. Broad read access weakens confidentiality and conflict-of-interest controls. | 1.8a; 1.9a; Annexure-16 | M |
| RB-08 | No committee membership, quorum, conflict declaration, random selection or co-option record. | APH specifies compositions and quorums (EC one-third; SCSC any two), automated member selection, and a co-option rule for State/UT/affiliating-university representatives. | Annexure-16 (16.1-16.8, NOTE); 1.8a; 1.9a | L |
| RB-09 | One institution login represents the applicant; no authorised representatives or DSC identity. | APH requires two authorised representatives with self-attested photo ID at Scrutiny/SHC/SAC and DSC-signed submissions. | 1.8c; 1.11d; 2.24e; 1.4.3 | L |
| RB-10 | No user/role administration endpoints; users exist only through seed data. | A demo cannot create a committee member, SHC/SAC member, EC member or new institution user through the product. | §1; Annexure-16 | M |
| RB-11 | `REGIONAL_HEAD` can edit compliance rules, RAG weights and alert rules' read views. | Norm-setting is an AICTE-level function; a regional officer should consume norms, not author them. This is a governance mismatch even where APH is silent on UI ownership. | §7; project rule 2 (rules are data, administered centrally) | S |

### 2.4 Missing role capabilities

| ID | Missing capability | Why it matters | Effort |
|---|---|---|---|
| RB-M1 | Split `SCRUTINY_OFFICER` into `REGULATION_BUREAU_OFFICER` and `SCRUTINY_COMMITTEE_MEMBER`. | Correct scheduling vs adjudication separation. | M |
| RB-M2 | Replace `INSPECTION_COMMITTEE` with `EVC_MEMBER` plus committee/visit membership. | Multi-member EVC, quorum and conflict checks. | L |
| RB-M3 | Replace `REGIONAL_HEAD` decision powers with `REGIONAL_OFFICER` (EVC constitution) plus `EXECUTIVE_COMMITTEE_MEMBER` (decision). | EC decides; Council ratifies. | L |
| RB-M4 | Add `SHC_MEMBER`, `SAC_MEMBER`, `COMPLAINT_SCRUTINY_MEMBER` and Council secretariat permissions. | Hearings, appeals and complaints cannot be represented. | L |
| RB-M5 | Add committee membership, quorum, COI and random-selection services. | APH Annexure-16 compositions are not optional. | L |
| RB-M6 | Add applicant representative records and DSC registration. | Two representatives and signed submissions. | L |
| RB-M7 | Add admin user management and role assignment with audit. | Operational usability and separation of duties. | M |
| RB-M8 | Add explicit permission checks for "assigned to my committee", not only region. | Prevent cross-case access. | M |
| RB-M9 | Add Council/EC agenda and ratification permissions distinct from platform administration. | `SUPER_ADMIN` should not vote or decide. | M |

### 2.5 Role verdict

The RBAC implementation is clean for a five-role prototype: guards are centralized, scoping is server-side, and the workflow transition table owns action permissions. The **role model itself is the problem**. Renaming alone is not enough; committee membership, quorum and conflict data are required before the APH workflow can be enforced.

---

## 3. Application portal

### 3.1 Existing implementation

| Area | Files / endpoints |
|---|---|
| Tables | `applications`, `application_programs`, `documents`, `required_documents`, `institutions`, `users`, `audit_logs` |
| Draft creation and editing | `POST /applications`, `PATCH /applications/{id}`, `DELETE /applications/{id}` in `backend/app/api/routes/application_workspace.py` |
| Programmes | `GET/POST/PATCH/DELETE /applications/{id}/programs` |
| Documents | `GET/POST /applications/{id}/documents`, `GET /applications/{id}/documents/{document_id}/download`, `GET /applications/{id}/documents/checklist` |
| Completeness | `GET /applications/{id}/checklist`; `backend/app/services/application_sections.py` |
| Submission | `POST /applications/{id}/submit`; `backend/app/services/application_workspace.py` |
| Compliance preview | `POST /applications/{id}/compliance/preview` |
| Applicant list/detail | `GET /applications`, `GET /applications/{id}`; `frontend/src/pages/ApplicationsPage.tsx`, `ApplicationDetailPage.tsx` |
| Wizard UI | `frontend/src/pages/NewApplicationPage.tsx`, `ApplicationWizardPage.tsx` |

The portal collects six JSON sections (`institution_profile`, `infrastructure`, `faculty`, `finance`, `accreditation`, `mandatory_disclosure_url`) and programme rows (`program_name`, `level`, `intake`, `faculty_count`, `lab_count`). Seven generic document types are seeded per application type. Submission is blocked only by the completeness checklist: required fields, a valid mandatory-disclosure URL, and mandatory document uploads.

### 3.2 Portal contradictions and gaps

| ID | Current behaviour | Why it is a problem / APH contradiction | APH reference | Effort |
|---|---|---|---|---|
| AP-01 | Only `NEW` and `EXTENSION` can be created; `INTAKE_CHANGE` is enum-only. | APH Table 2.2/2.3 has 21 types; the portal cannot start most of them. | §2; Tables 2.2/2.3 | L |
| AP-02 | No application fee, TER calculator or payment gate. Submission succeeds without payment. | APH: unpaid applications are not considered; TER is due by the cut-off and varies by type/category. | 1.4.2e-f; §4; Tables 1.1/2.1 | L |
| AP-03 | No DSC/e-sign on uploads or submission; no Affidavit 2. | APH: all documents digitally signed; no DSC means no submission; Affidavit 2 is mandatory. | 1.4.3; 1.4.5; §8 | L |
| AP-04 | No copy to State Government/UT and affiliating university/board with sealed receipt. | Explicit submission step in APH. | 1.4.5 | M |
| AP-05 | A generated `APP-YYYY-XXXXXXXX` reference exists inside JSONB, but it is not an immutable APH application number and there is no public/status-tracker surface. | APH allots a unique application number and makes status trackable. | 1.4.1d; §3.1 step 2 | M |
| AP-06 | No public-notice cut-off or academic-calendar check. Any academic year can be submitted at any time. | APH submissions after the cut-off are processed for the next academic year; no EoA after the Academic Calendar last date. | 1.2; 2.2; 2.25j; Table 2.2 | M |
| AP-07 | Institution profile has no promoter/trust/society/company, registered address, campus/site, affiliation, government/aided/minority status. | Annexure-1 eligibility and naming/land rules depend on these. | 1.3.4; 1.5; 6.17; Annexure-1 | L |
| AP-08 | Infrastructure is five scalars: land area, built-up area, labs, library volumes, hostel beds. | APH needs land parcels/title/lease, room-wise areas, labs/equipment, library titles/volumes/journals, PCs, bandwidth and certificates. | 6.17-6.18; Annexure-3/4 | L |
| AP-09 | Faculty is six aggregate numbers, including a self-declared student-faculty ratio. | APH calculates required faculty from approved intake and programme ratio, then checks cadre 1:2:6, qualifications, regular/adjunct status and PG professor coverage. | 6.14; Annexure-5; §7.1 | L |
| AP-10 | Programmes are free-text name + four numbers. | APH uses approved nomenclature, level, division, shift, course duration and year-wise intake; existing institutions need current approved intake and the requested change. | Table 1.3; §10; 2.6-2.7 | L |
| AP-11 | No type-specific form, self-disclosure, deficiency report acknowledgement, undertaking or affidavit set. | Table 2.3 and Annexure-1/2 vary by type; Affidavit 2 and type-specific affidavits are mandatory. | §2 Table 2.3; §8 | L |
| AP-12 | Submission changes the status and blocks further draft edits, but no immutable submitted snapshot/version is stored; compliance re-evaluates live data. | APH: edit allowed until final submission, then the submitted application is locked and must remain auditable. | 1.4.3 | M |
| AP-13 | No withdrawal/revocation flow with refund windows and penalties. | APH has a 7-day post-payment revocation window, a 10 April closure-withdrawal date, and refund-minus rules. | 2.3.3f-g; 1.4.2h | L |
| AP-14 | No post-submission deficiency-response surface in the wizard; deficiencies are handled only in the case file. | Applicants need to see and respond to the Deficiency Report before Scrutiny/Re-Scrutiny/SHC. | 2.3.3b; 2.4 | M |
| AP-15 | No status tracker or letter download for the applicant. | APH requires status tracking and portal publication/download of LoA/EoA, LoD/LoR and Speaking Orders. | 1.4.1d; 1.10; 2.25k | M |

### 3.3 Missing portal features

| ID | Missing feature | Minimum useful slice | Effort |
|---|---|---|---|
| AP-M1 | Type catalogue and type-driven form | `application_types` seeded from §2; show only supported types, with a clear "not yet implemented" state for the rest. | M |
| AP-M2 | TER calculator and payment record | Fee rule table, category/type/division inputs, computed amount, payment status gate before submit. | L |
| AP-M3 | DSC/Affidavit 2 | DSC registration flag + Affidavit 2 upload/acceptance; block submit without both. | M |
| AP-M4 | Unique application number | Human-readable number generated at submit, immutable and searchable. | S |
| AP-M5 | Cut-off calendar | Configurable public notice/academic calendar; block or warn on late submission. | M |
| AP-M6 | Type-specific document checklist | Annexure-1/2 matrix keyed by type and stage (scrutiny vs EVC vs post-LoA). | L |
| AP-M7 | Deficiency Report response | Applicant view of report, item-level response and evidence upload. | M |
| AP-M8 | Submitted snapshot and lock | Freeze submitted JSON + document version IDs; reject edits after submit. | M |
| AP-M9 | Withdrawal/refund request | Request, reason, time-window check, refund calculation, audit. | L |
| AP-M10 | Status tracker and letters | Applicant timeline, letter list, download and acknowledgement. | M |
| AP-M11 | State/university copy acknowledgement | Upload sealed receipt / record dispatch. | S |

### 3.4 Portal verdict

The draft/save/upload/submit loop is usable and well-tested. It is a **generic grant application**, not an AICTE application. The most damaging demo gap is the absence of a payment/DSC gate: APH treats both as preconditions, so a submitted case without them is visibly non-compliant.

---

## 4. Workflow engine

### 4.1 Existing implementation

| Area | Files / symbols |
|---|---|
| Single state machine | `backend/app/services/workflow.py` → `TRANSITIONS`, `Transition`, `WorkflowService` |
| Tables | `applications`, `workflow_events`, `deficiencies`, `inspections`, `sla_configs`, `audit_logs` |
| Status/action/stage enums | `backend/app/models/enums.py` |
| API surface | `POST /applications/{id}/actions/{action}`; `GET /applications/{id}/timeline`; `GET /applications/{id}/allowed-actions`; `GET /applications/{id}/deficiencies`; `GET /applications/{id}/inspections`; `GET /applications/{id}/committee-members`; `POST /applications/{id}/submit` (workspace route) |
| Schemas | `backend/app/schemas/workflow.py` |
| History/audit | `workflow_events`, `audit_logs`; `WorkflowService._record_transition` |
| SLA | `SLAConfig`; `WorkflowService._sla_due_at`; `backend/app/services/scheduler.py` |
| Tests | `backend/tests/test_workflow.py`, `test_authorization.py`, `test_application_workspace.py` |

The engine is genuinely centralized: routes do not set `Application.status` directly, every transition is declared in `TRANSITIONS`, role and scope checks run before dispatch, and each action writes a `WorkflowEvent` plus an `AuditLog`. This is the strongest part of the codebase.

Current path:

```
DRAFT
  └─ submit → SUBMITTED
       └─ auto_assign → DOCUMENT_VERIFICATION
            └─ verify_documents → SCRUTINY
                 ├─ raise_deficiency → DEFICIENCY_RAISED
                 │    └─ respond_deficiency → DEFICIENCY_RESPONDED
                 │         └─ close_deficiency → SCRUTINY
                 └─ schedule_inspection → INSPECTION_SCHEDULED
                      └─ submit_inspection_report → INSPECTION_DONE
                           └─ send_to_committee → COMMITTEE_REVIEW
                                ├─ approve → APPROVED
                                ├─ conditionally_approve → CONDITIONALLY_APPROVED
                                └─ reject → REJECTED
```

`withdraw` is an overlay action available to the institution in any non-terminal status.

### 4.2 Workflow contradictions and gaps

| ID | Current behaviour | Why it is a problem / APH contradiction | APH reference | Effort |
|---|---|---|---|---|
| WF-01 | Linear path has no Re-Scrutiny, SHC, EC, Council, appeal/SAC or post-decision state. | The Annexure-7 flow is Scrutiny → Re-Scrutiny (if deficiency) → EVC → EC → Council ratification → LoA/LoD/LoR, with an appeal route to SAC. | §3.1 steps 4-8; §3.2; 1.8-1.11; 2.23.3-2.24a | L |
| WF-02 | Submission auto-assigns the least-loaded `SCRUTINY_OFFICER` in the region. | APH selects a Scrutiny Committee through an automated web-portal process with prescribed composition, not a single load-balanced officer. | 1.8a; Annexure-16 (16.3-16.4) | L |
| WF-03 | A separate `DOCUMENT_VERIFICATION` stage precedes scrutiny and is performed by one officer. | Document authenticity verification is the Scrutiny/Re-Scrutiny Committee's job (Annexure 1/2); the Regulation Bureau schedules it. | 1.8; Annexure-1/2 | M |
| WF-04 | `INSPECTION_SCHEDULED` assigns one `INSPECTION_COMMITTEE` user and a free-form report. | EVC is a multi-member committee; it verifies infrastructure, faculty, equipment and library online/physical and checks only approved-intake capacity. | 1.9a-f; Annexure-16 (16.5); Ch. VIII point 7 | L |
| WF-05 | `REGIONAL_HEAD` performs `send_to_committee`, `approve`, `conditionally_approve` and `reject`. | EC takes the approval decision; Council ratifies. The Regional Officer's role is to constitute the EVC, and the Regional Committee endorses LoA/LoR. | 1.10a; Definitions 29; Annexure-7 | L |
| WF-06 | No Council ratification step or recorded ratification. | EC decisions must be placed before Council; Council ratification is part of the decision. | 1.10a; 2.25a | L |
| WF-07 | `conditionally_approve` is a first-class terminal action with a free-text conditions field. | APH says no conditional approval normally and no partial approval. Conditions belong to post-approval compliance, not the letter type. | 4.9c; 2.27; 4.4.3 note | M |
| WF-08 | `reject` produces one `REJECTED` state and stores the decision in JSONB. | APH distinguishes LoD and LoR, requires a Speaking Order, publishes the decision on the portal, and starts a 7-day appeal clock. | 1.10; 1.11a; 2.24a | L |
| WF-09 | `approve` ends the workflow. There is no LoA issue, no Security Deposit, no Affidavit 3 and no Regional Committee endorsement. | LoA is issued after EC/Council; the institution must deposit the Security Deposit and Affidavit 3 within 15 days or face 10%/20% penalties and withdrawal. | 1.10; 1.12; 2.25f; §3.1 steps 8-9 | L |
| WF-10 | No appeal action or SAC hearing after a decision. | An appeal is allowed once within 7 days of LoD issue/decision upload; SAC can recommend, not recommend, or send back; Council is final. | 1.11a-e; 2.24a; Annexure-7 | L |
| WF-11 | No SHC hearing stage. | Existing-institution compliance and EVC deficiencies go to SHC before EC; complaints also route through SHC. | 2.23.3; 7.10; Annexure-16 (16.8) | L |
| WF-12 | No complaint, show-cause, penal-action or restoration workflow. | APH defines PGRC→SCSC→SHC→EC complaints, penal actions with a hearing, and restoration after punitive action. | 7.10; §9; 7.11-7.12 | L |
| WF-13 | No closure, hibernation, break-in-EoA, restoration, change-of-site or merger flows. | These are distinct APH tracks with their own documents, EVC rules and deadlines. | 2.13-2.21; 2.16.1; 3.4 | L |
| WF-14 | No EoA-on-self-disclosure path or extended-EoA eligibility check. | Existing institutions can get EoA on self-disclosure (with random EVC) or a three-year extended EoA if one of six criteria is met. | 2.5; 2.3.5a; 2.1a | L |
| WF-15 | `withdraw` is an institution action available in any non-terminal status; it does not calculate refunds or enforce dates. | APH limits revocation after payment to 7 days, limits withdrawal of a pending closure to 10 April, and defines refund-minus amounts. | 2.3.3f-g; 1.4.2h | L |
| WF-16 | SLA is one duration per internal stage, with a generic escalation role. | APH deadlines are event-specific and legally meaningful: 7-day appeal, 15-day deposit, 30 November enrolment, 30 June IC report, 12-month vacancy triggers. | §5; 1.11a; 2.24a; 2.25f/n; 6.48g | L |
| WF-17 | `raise_deficiency` creates ad-hoc rows; `close_deficiency` returns directly to scrutiny. | APH requires a Deficiency Report, a chance to comply, and Re-Scrutiny that verifies only the listed deficiencies. | 2.3.3b; 2.4; 1.8 | L |
| WF-18 | No committee quorum, conflict-of-interest, co-option or recusal checks. | Annexure-16 sets compositions and quorums; members are selected by portal process and can be co-opted. | Annexure-16 (16.1-16.8, NOTE) | L |
| WF-19 | `SUPER_ADMIN` is a member of every transition role set. | A platform administrator can approve a case without EC, Council or committee involvement, defeating separation of duties. | §1; 1.10a | M |
| WF-20 | The engine's terminal states are private statuses (`APPROVED`, `REJECTED`), not APH instruments (`LoA`, `LoD`, `LoR`). | The legal output is a letter with a Speaking Order; a status badge is not an approval. | 1.10; 1.11e; 2.24a | M |
| WF-21 | No decision deadline tied to the Academic Calendar last date. | APH: no EoA after the Academic Calendar last date; letters are issued on or before that date. | 2.25j; §3.1 step 6 | M |
| WF-22 | Stage `DECISION` exists in `WorkflowStage` and `SLAConfig` but is never used by `_stage_for`. | Dead configuration is misleading and will collide with a real EC/Council decision stage. | Project consistency; APH §3.1 step 6 | S |

### 4.3 Missing workflow capabilities

| ID | Missing capability | Minimum useful slice | Effort |
|---|---|---|---|
| WF-M1 | Re-Scrutiny round | `scrutiny_rounds`; deficiency-only re-check; new event/action. | M |
| WF-M2 | EVC visit | Multi-member assignment, schedule, checklist, report, recommendation. | L |
| WF-M3 | SHC hearing | Case referral, hearing record, outcome, re-check. | L |
| WF-M4 | EC decision and Council ratification | Agenda, quorum, vote/decision, ratification record. | L |
| WF-M5 | Decision letters | LoA/LoD/LoR + Speaking Order templates, issue, publish, acknowledge. | L |
| WF-M6 | Appeal/SAC | 7-day timer, appeal filing, SAC hearing, send-back loop, Council final. | L |
| WF-M7 | Security Deposit | Intimation, 15-day timer, proof/Affidavit 3, penalty ladder, release. | L |
| WF-M8 | Complaints/penalties | PGRC, SCSC, show-cause, SHC, EC, penal action. | L |
| WF-M9 | Closure/hibernation/restoration | Separate state machines and document sets. | L |
| WF-M10 | Deadline calendar | Configurable event deadlines, not stage SLAs. | M |
| WF-M11 | Withdrawal/refund | Time-window checks and refund calculation. | M |
| WF-M12 | Committee/quorum/COI guards | Data-driven composition and conflict checks. | L |
| WF-M13 | Remove `SUPER_ADMIN` from operational transitions | Platform admin can read/configure, not decide. | S |
| WF-M14 | Retire `DECISION` or implement it | Use `DECISION` for EC/Council or remove it from config. | S |

### 4.4 Workflow verdict

The **mechanism is good; the process is wrong**. Keeping the single `TRANSITIONS` authority is the right architectural choice. The four-day fix is to replace the transition table and status vocabulary, not to add ad-hoc endpoints. The committee/letter/deposit branches can be thin but must be real records, not comments in `details`.

---

## 5. Compliance engine

### 5.1 Existing implementation

| Area | Files / symbols |
|---|---|
| Rule evaluation | `backend/app/services/compliance.py` → `evaluate_application`, `evaluate_institution`, `run_nightly_evaluation` |
| Rule/config administration | `backend/app/api/routes/compliance_admin.py`, `backend/app/services/compliance_admin.py` |
| Models | `ComplianceRule`, `ComplianceResult`, `ComplianceConfig`, `ComplianceSnapshot` |
| Seed rules | `backend/app/seed.py` → `COMPLIANCE_RULES`, `COMPLIANCE_DEFAULT_CONFIG` |
| API | `/compliance/rules`, `/compliance/metrics`, `/compliance/config`, `/compliance/monitor`, `/compliance/monitor/run`, `/compliance/institutions/{id}/trend`; case evaluation at `GET /applications/{id}/compliance`; draft preview at `POST /applications/{id}/compliance/preview` |
| UI | `frontend/src/pages/ComplianceAdminPage.tsx`, `frontend/src/components/casefile/CaseCompliance.tsx`, `frontend/src/components/application/CompliancePreviewPanel.tsx` |
| Tests | `test_compliance_engine.py`, `test_compliance_admin.py`, `test_compliance_monitor.py`, `test_compliance_preview.py` |

The engine is a **configurable threshold rule system**:

- 15 seeded rules across Infrastructure, Faculty, Finance, Accreditation and Documents.
- 24 metric keys, mostly raw values from the JSONB form, plus derived values: total intake, qualified-faculty percentage, built-up area per student, library volumes per student, labs per programme, NAAC/NBA presence, mandatory-disclosure URL presence and document validity.
- Operators `<`, `<=`, `=`, `==`, `>=`, `>`, `!=`, `BETWEEN`, `EXISTS`.
- Weighted 0-100 score from severity weights; RED below 70 or any failed CRITICAL, AMBER below 85, otherwise GREEN. All three values are editable.
- Results are replaced on each evaluation; an institution-level snapshot is appended for trend charts.
- A worsening to RED can create `COMPLIANCE_RED` alerts.
- The nightly job re-evaluates each institution against its **most recent application**.

### 5.2 Compliance contradictions and gaps

| ID | Current behaviour | Why it is a problem / APH contradiction | APH reference | Effort |
|---|---|---|---|---|
| CE-01 | Fifteen illustrative thresholds such as land ≥ 8,000 sqm, built-up ≥ 5,000 sqm, total faculty ≥ 60, student-faculty ratio ≤ 20, PhD faculty ≥ 30%, fee band ₹20,000-₹2,00,000. | These are demo numbers, not APH norms. APH formulas depend on programme, level, approved intake, cadre and infrastructure inventory. | §7.1-§7.4; Annexure-3/4/5 | L |
| CE-02 | The institution self-declares `student_faculty_ratio`; the engine does not compute it. | APH computes required faculty from `S = sum of approved intake across all years` divided by the programme/level ratio. A declared ratio can be gamed. | 6.14; Annexure-5; §7.1 | L |
| CE-03 | Faculty is six aggregate numbers. | APH needs a faculty roster with designation, qualification, regular/adjunct status, pay/ECS, PhD, department and student load, then checks cadre 1:2:6, the 25% reduction rule, adjunct caps and PG Professor coverage. | 6.14a-j; Annexure-5; §7.1 | L |
| CE-04 | Built-up area is one scalar checked against 5,000 sqm. | APH built-up area is instructional + administrative + amenities carpet area plus ~25% access/circulation, with room-wise minimums by programme, divisions and intake. | 6.17-6.18; Annexure-3 §3.2 | L |
| CE-05 | Laboratories are a count; library is a volume count; hostel is a bed count. | APH specifies labs by course/year/intake, equipment, book titles/volumes, journals, reading-room seats, e-books, PCs, printers, language labs and bandwidth. | Annexure-4; §7.3 | L |
| CE-06 | No essential-requirements checks. | APH 6.47-6.53 require Anti-Ragging, IC, SC/ST committee, grievance/SGRC/Ombudsperson, IIC, barrier-free access, ABC, safety, food safety, digital payments, letter display, counselling, women's helpline, medical, water, waste, insurance, internship, SWAYAM, skilling, industry cell, language lab and IQAC. | 6.47-6.53; §7.4 | L |
| CE-07 | Mandatory disclosure is a single URL-presence check. | Annexure-18 requires a structured, dynamically updated disclosure with governance, programmes, faculty profiles, fees, admissions, infrastructure, enrolment, placement, research and MoUs. | Annexure-18; §7.4 | L |
| CE-08 | No Board of Governors/Management composition check. | Annexure-17 requires 11-21 members with specified trust, university, State, industry/educationist, Principal and faculty nominees, and periodic minutes. | Annexure-17; §7.4 | L |
| CE-09 | No eligibility or seat calculators. | APH needs extended-EoA criteria, NRI 5%, FN/OCI 15%, lateral 10%, TFW 5%, EWS, working-professional and regional-language divisions, and maximum-intake checks. | 2.1a; 2.6; 2.8-2.10; 6.13; 6.37-6.44; Table 1.3; §11 | L |
| CE-10 | Rules apply to `ALL`; `applies_to` is a free string with no programme/level/status semantics. | APH norms vary by programme (E&T, Management, Planning, Design, HMCT, Computer Applications), level (Diploma/UG/PG), intake and institution type. | §7; Annexure-3/4/5 | M |
| CE-11 | Rules have no APH clause reference, formula version or effective date. | A compliance result cannot be traced to the norm it enforces, and historical results cannot be reproduced after an edit. | §7; 6.53; project audit requirement | M |
| CE-12 | A failed rule is just `passed = false`; there is no evidence, source document, reviewer or override. | EVC/EC/SHC need to see why a value was accepted or rejected; APH documents must be verified against evidence. | 1.9e; 6.53; Annexure-1/2 | L |
| CE-13 | `NOT_ASSESSED` is reported as incomplete, not as a blocking failure. | Missing mandatory evidence should prevent "nil deficiency", not merely lower a score. | 2.4; 2.23.3; 6.53 | M |
| CE-14 | Institution monitoring evaluates the most recent application, not an approved-intake/enrolment ledger. | Post-approval compliance is annual and programme-level; a single latest application is not the institution's approved status. | 2.25b/k/n; 6.12; 7.4 | L |
| CE-15 | RAG is a project-defined score; a GREEN score can coexist with an unassessed mandatory requirement. | APH compliance is a set of mandatory yes/no conditions and formula checks, not a weighted satisfaction score. RAG can remain as a UI summary only if mandatory failures always dominate. | 6.47-6.53; 2.4 | M |
| CE-16 | Document validity uses expiry dates only. | APH has specific validity rules: Structural Stability Certificate after 30 years valid 5 years; provisional Occupancy Certificate for 2 academic years; Fire Safety and other certificates as applicable. | 6.17h; Annexure-3 §3.1c; Annexure-2.1 | M |
| CE-17 | No penalty recommendation from failures. | APH penal actions are triggered by specific violations and require a hearing and speaking order. | §9; 7.3-7.4; 6.50h proviso | L |
| CE-18 | No "nil deficiency" report or scrutiny checklist output. | APH scrutiny ends in nil deficiency or a Deficiency Report; the compliance engine should feed that output. | 2.3.3b; 2.4; 1.8 | M |
| CE-19 | No new-institution eligibility checks: promoter type, land title/lease, financial fund position, programme composition. | APH new-institution eligibility is a precondition to scrutiny. | 1.3.4; 1.5.3; 1.7.1; 6.17; Table 1.2 | L |
| CE-20 | No programme-level accreditation/NBA validity checks for extended EoA or FPM. | Extended EoA and FPM eligibility depend on NBA/NAAC/NIRF/QS/autonomy/enrolment criteria. | 2.1a; 2.12; §10 | M |

### 5.3 Missing compliance capabilities

| ID | Missing capability | Minimum useful slice | Effort |
|---|---|---|---|
| CE-M1 | Faculty requirement calculator | Inputs: programme, level, years, approved intake, division size; output: S, required faculty, cadre split, 25% reduction, adjunct cap. | L |
| CE-M2 | Faculty roster and qualification checks | Roster table, regular/adjunct, PhD, designation, department, ECS/pay proof, PG Professor coverage. | L |
| CE-M3 | Built-up area calculator | Room inventory and formulas for instructional/admin/amenities + 25% circulation; programme-specific room sizes. | L |
| CE-M4 | Library/PC/bandwidth calculator | Titles/volumes, journals, reading seats, e-books, PCs, printers, language lab, bandwidth by intake. | L |
| CE-M5 | Essential-requirements checklist | 6.47-6.53 yes/no items with evidence, owner, validity and reviewer. | L |
| CE-M6 | BoG and mandatory-disclosure checker | Structured BoG composition and Annexure-18 field checklist with public URL and PDF check. | L |
| CE-M7 | Eligibility/seat calculators | Extended EoA, NRI/FN/OCI, lateral, TFW, EWS, working-professional, regional-language, maximum intake. | L |
| CE-M8 | Clause-linked, versioned rules | `aph_clause`, `formula`, `effective_from`, `version`, `programme/level` applicability; immutable result snapshots. | M |
| CE-M9 | Evidence-linked results | Link each result to documents/roster/rooms and capture reviewer/override. | L |
| CE-M10 | Post-approval monitoring | Approved-intake ledger, annual data, enrolment, faculty updates, compliance case history. | L |
| CE-M11 | Deficiency/nil-deficiency report | Generate a scrutiny checklist/report from rule results and observations. | M |
| CE-M12 | Penalty recommendation | Map confirmed violations to §9 actions, with hearing and speaking order. | L |

### 5.4 Compliance verdict

The engine is a good **generic rules platform** and the admin UX is stronger than most hackathon prototypes. It is not an APH compliance engine. The four-day slice should add **two real calculators** (faculty and built-up area) and the **essential-requirements checklist**, then label the remaining rules as illustrative. Trying to encode all of Annexure-3/4/5 in four days will produce unverified formulas, which is worse than an honest partial implementation.

---

## 6. Alert engine

### 6.1 Existing implementation

| Area | Files / symbols |
|---|---|
| Engine | `backend/app/services/alert_engine.py` → `AlertEngine`, `run_alert_scan`, `notify_workflow_event`, `create_compliance_red_alerts`, `acknowledge_alert` |
| Scheduler | `backend/app/services/scheduler.py` → 15-minute alert scan; nightly compliance evaluation |
| Models | `AlertRule`, `Alert`, `AlertTrigger`, `AlertChannel`, `AlertStatus` |
| Seed rules | `backend/app/seed.py` → `ALERT_RULES`, `SLA_CONFIGS` |
| API | `GET /alerts/summary`, `GET /alerts`, `POST /alerts/{id}/ack`; `GET/POST/PATCH/DELETE /alert-rules` |
| UI | `frontend/src/pages/AlertsPage.tsx`, `AlertRulesPage.tsx`, `NotificationBell.tsx`, `EscalationBadge.tsx` |
| Tests | `test_alert_engine.py`, `test_alerts.py`, `test_dev_time.py` |

The engine is **rule-driven and operationally solid**:

- Eight trigger types: deadline approaching, SLA breached, deficiency due, deficiency overdue, document expiring, compliance RED, application status changed, inspection scheduled.
- Eleven seeded rules, including 7/3/1-day deadline warnings and 30/15-day document-expiry warnings.
- One row per recipient and channel; in-app, SMTP email (Mailpit in development) and a mock SMS provider behind an interface.
- Deduplication by `dedupe_key`; periodic scans are idempotent.
- A two-step escalation chain: initial recipient → `REGIONAL_HEAD` (the rule's escalation role is constrained to regional/super) → `SUPER_ADMIN`; escalation level and parent alert are stored, and a workflow event records the escalation.
- Alert rules, templates, channels, severity and escalation role are editable from the UI.

### 6.2 Alert contradictions and gaps

| ID | Current behaviour | Why it is a problem / APH contradiction | APH reference | Effort |
|---|---|---|---|---|
| AL-01 | Triggers are generic case SLAs, deficiency dates, document expiry, compliance RED and status changes. | APH alerts must cover statutory events: cut-off, appeal, deposit, committee hearings, EC/Council decisions, enrolment, complaints, annual reports and penal-action clocks. | §5; 1.11a; 2.24a; 2.25f/n; 6.48g; 7.13 | L |
| AL-02 | No 7-day appeal timer after LoD/decision upload. | The appeal is allowed once within 7 days; the clock must start from a configurable event (issue vs upload, per §12 ambiguity). | 1.11a; 2.24a; §12 item 2 | M |
| AL-03 | No Security Deposit intimation or 15-day/31 May/31 July penalty ladder. | APH requires proof and Affidavit 3 within 15 days, then 10% up to 31 May and 20% up to 31 July, then withdrawal. | 2.25f; 1.12 | L |
| AL-04 | No 30 November enrolment, 30 June IC annual report, monthly complaint/grievance report, 10 April closure withdrawal, 15-day affiliating-body views, 30 April restoration, 12-month vacancy or faculty-shortfall clocks. | These are explicit APH deadlines and triggers for penal action. | §5; 2.3.3g; 2.19c; 7.12; 7.4b-c; 6.48g; 7.13 | L |
| AL-05 | Escalation is officer → `REGIONAL_HEAD` → `SUPER_ADMIN`, with a configurable role. | APH escalation follows the process: Regulation Bureau → committee/SHC → EC → Council; complaints go PGRC → SCSC → SHC → EC; appeals go SAC → Council. A generic regional-head chain cannot represent this. | §1; 1.10a; 1.11e; 2.23.3; 7.10 | L |
| AL-06 | `AlertTrigger` is an enum and `alert_rules.trigger_type` has a hard-coded `CHECK`. | Adding an APH deadline requires code and a migration, violating the project rule that business rules are data. | §5; project `AGENTS.md` rule 2 | M |
| AL-07 | No hearing notice, agenda, quorum reminder, decision-publication or speaking-order alert. | Committees and the institution must be informed of scrutiny/EVC/SHC/SAC/EC dates and decisions. | 1.8; 1.9; 2.23.3; 2.24a; 7.10 | L |
| AL-08 | A normal status change notifies `_initial_recipients` (assigned officer or regional head), not the institution. | The applicant needs to know about deficiencies, decisions, letters and appeal windows. Only the deficiency branch explicitly targets the institution admin. | 1.4.1d; 1.10; 2.24a | M |
| AL-09 | Deadlines are `days_before` integers from a stage SLA; there is no calendar, working-day or event-date model. | APH deadlines are tied to public notices, academic calendars and event dates, not stage age. | §5; 1.2; 2.2; 2.25j | M |
| AL-10 | No letter/notice templates for LoA/LoD/LoR, Deficiency Report, show-cause, appeal acknowledgement or Speaking Order. | These are the official communications; a generic status message is not a substitute. | 1.10; 1.11; 2.3.3b; 7.10 | L |
| AL-11 | Escalation only raises another alert; it does not reassign the case, schedule a hearing or create a committee task. | An escalation that does not change accountability is only a notification. | §1; 1.10a; 7.10 | M |
| AL-12 | Alerts are a personal inbox; there are no role/committee queues or "unacknowledged by committee" views. | Committees work from case queues and agendas, not individual inboxes. | 1.8a; 1.9a; Annexure-16 | M |
| AL-13 | Email/SMS delivery has no durable outbox, retry/backoff or dead-letter state. | Demo-acceptable, but a statutory notice cannot depend on a best-effort in-process send. | Project reliability requirement; APH notices | M |
| AL-14 | Document-expiry alerts use a generic `expiry_date`; no APH validity rules. | Structural Stability (5 years after 30 years), provisional OC (2 academic years) and Fire Safety validity are specific. | 6.17h; Annexure-3 §3.1c | M |
| AL-15 | No alert when a committee fails quorum, a member has a conflict, or a decision misses the Academic Calendar last date. | These are control failures that should be visible immediately. | Annexure-16; 2.25j | M |
| AL-16 | No penalty, forfeiture or deposit-release alerts. | APH has 10% early-encashment penalty, 10%/50% closure penalties, forfeiture and release clearances. | 7.7; 2.21; 6.46 | L |
| AL-17 | No monthly complaint/grievance status report reminder or public-disclosure update reminder. | APH requires a monthly online status report and dynamic mandatory disclosure. | 7.13; Annexure-18 | M |
| AL-18 | Alert copy is generic and sometimes addresses oversight only ("review the case"), not the actor who must act. | Notifications should state the required action, the clause and the consequence of missing the deadline. | §5; §9 | S |

### 6.3 Missing alert capabilities

| ID | Missing capability | Minimum useful slice | Effort |
|---|---|---|---|
| AL-M1 | Statutory deadline catalogue | Event-driven deadline rows seeded from §5, with start event, duration, grace/penalty ladder and owner. | L |
| AL-M2 | Appeal and deposit clocks | Create timers on decision/deposit intimation; escalate at 7/15 days and penalty dates. | M |
| AL-M3 | Committee/hearing notices | Scrutiny/EVC/SHC/SAC/EC scheduling, agenda, quorum and outcome notices. | L |
| AL-M4 | Applicant notification branch | Send decision/letter/deficiency/appeal notices to the institution's authorised representatives. | M |
| AL-M5 | Role/committee queues | Queue views by committee and stage, with unacknowledged/overdue counts. | M |
| AL-M6 | Decision-letter notifications | Publish and notify LoA/LoD/LoR and Speaking Order availability. | M |
| AL-M7 | Annual compliance reminders | 30 November enrolment, 30 June IC report, monthly complaint report, mandatory-disclosure update. | M |
| AL-M8 | Delivery outbox/retry | Durable email/SMS queue with status, retry and dead-letter. | M |
| AL-M9 | Penalty/release alerts | Deposit overdue, penalty applied, release clearance, forfeiture. | L |
| AL-M10 | Configurable trigger catalogue | Replace enum/CHECK with a trigger table and handler key. | M |

### 6.4 Alert verdict

This is the most complete operational subsystem in the repository. The alert **plumbing** (dedupe, channels, acknowledgement, escalation levels, scheduler, demo clock) is reusable. The **event model** is the gap: APH alerts are legal clocks attached to process events, not generic stage-age warnings. Reusing the plumbing while replacing the trigger catalogue is the right four-day strategy.

---

## 7. UI shell

### 7.1 Existing implementation

| Area | Files / components |
|---|---|
| App shell | `frontend/src/components/AppLayout.tsx`; `frontend/src/App.tsx` |
| Navigation and labels | `frontend/src/lib/roles.ts` → `ROLE_LABELS`, `ROLE_SCOPE_DESCRIPTIONS`, `ROLE_NAV` |
| Route guards | `frontend/src/components/ProtectedRoute.tsx`, `RequireRoles.tsx` |
| Login | `frontend/src/pages/LoginPage.tsx` (demo account picker, public stats) |
| Dashboard | `frontend/src/pages/OverviewPage.tsx` |
| Applications list | `frontend/src/pages/ApplicationsPage.tsx` |
| Admin surfaces | `ComplianceAdminPage.tsx`, `AlertRulesPage.tsx`, `AuditLogsPage.tsx` |
| Cross-cutting UI | `NotificationBell.tsx`, `CommandPalette.tsx`, `DemoTimeControl.tsx`, `KeyboardShortcutsDialog.tsx` |

The shell is polished: responsive sidebar, role-labelled navigation, global search, command palette, notification bell, demo time control and keyboard shortcuts. The five role navigations share the same application list with different labels ("Scrutiny queue", "Assigned inspections", "Regional applications", "All applications").

### 7.2 Shell contradictions and gaps

| ID | Current behaviour | Why it is a gap | APH reference | Effort |
|---|---|---|---|---|
| UI-01 | Navigation is generated from five roles. | No Regulation Bureau, Scrutiny Committee, EVC, SHC, SAC, SCSC, EC or Council workspace. | §1; Annexure-16 | L |
| UI-02 | All non-institution roles land on a generic "Recent applications" dashboard. | Each APH actor needs a task queue: scrutiny assignments, EVC visits, SHC hearings, SAC appeals, EC agenda, Council ratification, SCSC complaints. | 1.8a; 1.9a; 2.23.3; 2.24a; 7.10 | L |
| UI-03 | `REGIONAL_HEAD` has "Regional applications", compliance and audit screens. | The label and powers do not match the APH Regional Officer/Regional Committee distinction; decision work is missing from EC/Council. | Definitions 29; 1.10a; Annexure-7 | M |
| UI-04 | No public applicant registration, public status tracker or letter download. | APH starts with NSW portal registration and a trackable application number; decisions and letters are published/downloadable. | 1.4.1; 1.4.1d; 2.25k | M |
| UI-05 | No master-data administration: application types, document matrix, fee tables, deadlines, committee compositions, affidavit templates. | These are APH business rules and must be data-editable; only compliance/alert rules have admin screens. | §10; §2 Table 2.3; §4; §5; Annexure-16 | L |
| UI-06 | No SLA/deadline configuration screen, even though `sla_configs` is a table. | Administrators cannot change the statutory or internal clocks without direct database access. | §5; project rule 2 | M |
| UI-07 | No user/role/committee administration. | Cannot create an SHC member, EC member or new institution login through the product. | §1; Annexure-16 | M |
| UI-08 | No payment/TER, refund, Security Deposit, FDR or penalty screens. | The money lifecycle is entirely absent from the UI. | §4; 1.12; 2.25f; 6.46 | L |
| UI-09 | No decision-letter viewer, Speaking Order viewer, appeal filing or appeal timer. | The core legal outputs and the 7-day appeal are invisible. | 1.10; 1.11a; 2.24a | L |
| UI-10 | No complaint/PGRC/SCSC, show-cause, hearing or penal-action screens. | Complaints and penalties are a whole APH chapter and a likely demo question. | 7.10; §9 | L |
| UI-11 | No committee agenda, quorum, attendance, conflict declaration or minutes screen. | Committees cannot operate from the product. | Annexure-16; 1.8c; 2.24e | L |
| UI-12 | No APH letter/notice templates or generated PDFs. | The demo can show statuses but not an LoA/LoD/LoR. | 1.10; §8 | L |
| UI-13 | `SUPER_ADMIN` has no platform-admin home; it sees the same application dashboard plus compliance/alert/audit links. | Platform administration and Council secretariat are different jobs. | §1; 1.10a | M |
| UI-14 | No "application type" language or APH cut-off banner on the dashboard. | Users cannot tell which APH track they are in or whether the window is open. | 1.2; 2.2; Table 2.2 | S |

### 7.3 Missing shell capabilities

| ID | Missing capability | Minimum useful slice | Effort |
|---|---|---|---|
| UI-M1 | Role-specific queue pages | Scrutiny, EVC, SHC, SAC, EC, Council, SCSC queues with counts and due dates. | L |
| UI-M2 | Master-data admin | CRUD for types, document matrix, fee rules, deadlines and committee compositions. | L |
| UI-M3 | User/committee admin | Create users, assign roles/committees, manage COI. | M |
| UI-M4 | Payment/deposit screens | Fee computation, payment status, deposit intimation and release. | L |
| UI-M5 | Letters/appeals | Letter viewer, Speaking Order, appeal filing and countdown. | L |
| UI-M6 | Complaints/penalties | PGRC/SCSC queue, show-cause, hearing, penalty. | L |
| UI-M7 | Public tracker | Application-number lookup with status and letter availability. | M |
| UI-M8 | Calendar/deadline banner | Public notice, cut-off and academic calendar. | S |
| UI-M9 | APH-aligned labels | Replace "Regional head"/"Inspection committee" and private status names. | S |

### 7.4 Shell verdict

The shell is **production-quality UI for the wrong domain model**. The fastest high-value change is not a visual redesign; it is replacing the five role navigations with APH actor queues and adding the missing master-data/admin surfaces. A demo that shows an EC agenda and a letter viewer will communicate APH compliance better than another dashboard chart.

---

## 8. UI wizard

### 8.1 Existing implementation

`frontend/src/pages/NewApplicationPage.tsx` creates a draft with an application type (`NEW`/`EXTENSION`) and academic year. `frontend/src/pages/ApplicationWizardPage.tsx` implements eight steps from `frontend/src/lib/application.ts`:

1. Profile
2. Infrastructure
3. Faculty
4. Finance
5. Accreditation
6. Programmes
7. Documents
8. Review

The wizard auto-saves sections, validates on blur, shows a completeness rail/sidebar, previews compliance against unsaved values, lists required documents with upload/version status, and blocks submission on missing items. The review step shows the submission success panel.

### 8.2 Wizard contradictions and gaps

| ID | Current behaviour | Why it is a gap | APH reference | Effort |
|---|---|---|---|---|
| UW-01 | Only `NEW` and `EXTENSION` are offered. | The APH type catalogue is absent, so the wizard cannot route to type-specific forms. | §2; Table 2.2/2.3 | L |
| UW-02 | Eight fixed steps, identical for both types. | APH forms differ by type (self-disclosure, increase, new programme, site change, closure, etc.). | §2 Table 2.3; Annexure-1/2 | L |
| UW-03 | Profile lacks promoter/trust, registered address, campus/site, affiliation, government/aided/minority status. | These determine eligibility, naming, land rules and document set. | 1.3.4; 1.5; 6.17; Annexure-1 | L |
| UW-04 | Infrastructure is five scalars. | No land parcels/title/lease, room-wise built-up area, labs/equipment, library titles/volumes/journals, PCs, bandwidth or certificates. | 6.17-6.18; Annexure-3/4 | L |
| UW-05 | Faculty is six aggregate numbers and a self-declared ratio. | No roster, qualifications, regular/adjunct, department, pay/ECS, PhD or cadre validation. | 6.14; Annexure-5 | L |
| UW-06 | Programmes are free-text name + level + intake + faculty/lab counts. | No approved nomenclature, division, shift, duration, affiliation, NBA status, existing approved intake or requested change. | Table 1.3; §10; 2.6-2.7 | L |
| UW-07 | No TER/fee step, payment status or receipt. | Payment is a precondition to consideration. | 1.4.2e-f; §4 | L |
| UW-08 | No DSC/Affidavit 2/undertaking step. | No DSC means no submission; Affidavit 2 is mandatory. | 1.4.3; 1.4.5; §8 | L |
| UW-09 | No type-specific self-disclosure or deficiency report acknowledgement. | EoA-on-self-disclosure and "nil deficiency" tracks need them. | 2.5; 2.3.3b; 2.4 | M |
| UW-10 | No copy-to-State/affiliating-university acknowledgement. | Explicit APH submission step. | 1.4.5 | S |
| UW-11 | No cut-off/academic-calendar warning. | Late submissions are processed for the next academic year. | 1.2; 2.2; Table 2.2 | S |
| UW-12 | No submitted PDF/preview, unique application number or receipt. | Applicants need a durable submission record. | 1.4.1d; 1.4.3 | M |
| UW-13 | Review checks completeness, not APH eligibility (promoter, land, programme composition, fund position). | A complete but ineligible application can be submitted. | 1.3.4; 1.5.3; 1.7.1; Table 1.2 | L |
| UW-14 | No withdrawal/refund request. | APH has time-bound revocation/withdrawal. | 2.3.3f-g | M |
| UW-15 | No dedicated post-submission applicant workspace for the Deficiency Report, letters or status tracking; responses are possible only through the generic case file. | Applicant cannot follow the APH response-and-letter loop in a guided applicant view. | 2.3.3b; 2.4; 2.25k | M |
| UW-16 | The wizard exposes internal compliance previews and risk language to applicants. | APH scrutiny is an official process; showing draft internal scoring may confuse or bias. Keep it as an optional "self-check" clearly labelled illustrative. | 1.8; 2.4 | S |

### 8.3 Missing wizard capabilities

| ID | Missing capability | Minimum useful slice | Effort |
|---|---|---|---|
| UW-M1 | Type router and type-specific step registry | Start with NEW, EXTENSION and one existing-institution type (self-disclosure), with explicit unsupported states. | M |
| UW-M2 | Promoter/trust/campus/affiliation section | Capture eligibility and Annexure-1 identity data. | M |
| UW-M3 | Land/building inventory | Parcels, title/lease, rooms and areas; feed the area calculator. | L |
| UW-M4 | Faculty roster | CSV/manual roster with qualifications and regular/adjunct; feed FSR. | L |
| UW-M5 | Programme/division detail | Nomenclature, level, division, shift, duration, intake, NBA status. | L |
| UW-M6 | Fee/payment step | TER computation, payment record and receipt. | L |
| UW-M7 | DSC/Affidavit 2 step | Registration/upload and submit gate. | M |
| UW-M8 | Review PDF/application number | Generate a submission receipt and freeze the draft. | M |
| UW-M9 | Deficiency response | Item-level response and evidence upload. | M |
| UW-M10 | Withdrawal/refund | Request, reason, eligibility check and refund estimate. | M |

### 8.4 Wizard verdict

The wizard is a good **eight-step grant form** with excellent save/validation/document UX. It is not an APH application. The four-day slice should add the **type router**, **promoter/affidavit/DSC/payment gates**, and **one type-specific form**. Rebuilding all 21 types is not a four-day task and should not be attempted.

---

## 9. UI case file

### 9.1 Existing implementation

| Area | Files / components |
|---|---|
| Page | `frontend/src/pages/ApplicationDetailPage.tsx` |
| Header | `frontend/src/components/casefile/CaseFileHeader.tsx` |
| Stage track | `frontend/src/components/casefile/stages.ts` → `CASE_STAGES`, `buildStageEvents` |
| Tabs | `CaseOverview.tsx`, `CaseDocuments.tsx`, `CaseCompliance.tsx`, `CaseDeficiencies.tsx`, `CaseInspection.tsx`, `CaseTimeline.tsx` |
| Sidebar/actions | `frontend/src/components/casefile/CaseSidebar.tsx`; `frontend/src/components/workflow/WorkflowDialogHost.tsx` |
| Workflow dialogs | `frontend/src/components/workflow/` |

The case file has a seven-stage track:

```
APPLICATION → DOCUMENT_VERIFICATION → SCRUTINY → DEFICIENCY → INSPECTION → COMMITTEE_REVIEW → COMPLETED
```

It shows a header with reference, status, SLA ring, risk badge, escalation badge and an action menu; six tabs (Overview, Documents, Compliance, Deficiencies, Inspection, Timeline); and a sidebar with ownership, compliance risk, alerts and available actions. The action ownership map is:

```
submit, respond_deficiency, withdraw              → Institution admin
auto_assign, start_scrutiny, send_to_committee,
approve, conditionally_approve, reject            → Regional head
verify_documents, raise_deficiency,
close_deficiency, schedule_inspection             → Scrutiny officer
submit_inspection_report                          → Inspection committee
```

### 9.2 Case-file contradictions and gaps

| ID | Current behaviour | Why it is a gap | APH reference | Effort |
|---|---|---|---|---|
| CF-01 | Seven-stage track ends at `COMPLETED`; no Re-Scrutiny, EVC, SHC, EC, Council, LoA/LoD/LoR or appeal node. | The track tells a different process story from Annexure-7 and §3.2. | §3.1-§3.2; 1.8-1.11; 2.23.3-2.24a | L |
| CF-02 | The `DECISION` stage exists in the enum/SLA but is absent from `CASE_STAGES`. | A real EC/Council decision stage cannot be displayed; the current track would show an unknown current stage. | §3.1 step 6; project consistency | S |
| CF-03 | No decision tab, letter viewer or Speaking Order. | The legal outcome is invisible; the case file ends with a status badge. | 1.10; 1.11e; 2.24a | L |
| CF-04 | No appeal filing, 7-day countdown or SAC hearing panel. | The post-decision remedy is absent. | 1.11a-e; 2.24a | L |
| CF-05 | No Security Deposit panel, 15-day timer, Affidavit 3 or penalty ladder. | LoA is incomplete without the deposit lifecycle. | 1.12; 2.25f; 6.46 | L |
| CF-06 | No committee composition, attendance, quorum, conflict declaration or minutes. | Scrutiny/EVC/SHC/SAC/EC cannot be run or evidenced from the case file. | Annexure-16; 1.8c; 2.24e | L |
| CF-07 | No SHC/SAC/EC/SCSC hearing workspace. | The case file is built for an officer, not a committee. | 2.23.3; 2.24a; 7.10 | L |
| CF-08 | Inspection tab models one committee member and a free-form report; no EVC team, checklist, video URL, GPS coordinates or photos. | EVC evidence requirements are not represented. | 1.9a-g; Annexure-16 (16.5) | L |
| CF-09 | Deficiency tab is a flat list; no Deficiency Report, round, observation type or Re-Scrutiny linkage. | The applicant and committee cannot see the official deficiency report or which items were re-checked. | 2.3.3b; 2.4; 1.8 | L |
| CF-10 | No payment/TER, refund, FDR or penalty panel. | Money is part of the case lifecycle. | §4; 2.25f; 6.46 | L |
| CF-11 | No complaint/PGRC/SCSC/show-cause/penalty panel. | Complaints are a separate but related case type. | 7.10; §9 | L |
| CF-12 | No post-approval monitoring, approved-intake ledger or annual compliance panel. | The case file ends at approval, while APH continues monitoring and penal action. | 2.25; 6.12; 7.4 | L |
| CF-13 | Action owner labels and permissions reflect the five-role model, not APH. | `REGIONAL_HEAD` appears as decision-maker; `SUPER_ADMIN` can act; no EC/Council. | §1; 1.10a | M |
| CF-14 | Risk badge is derived from failed compliance rules, not APH risk or mandatory failures. | A GREEN/AMBER badge can mislead when an APH mandatory condition is unassessed. | 6.47-6.53; 2.4 | M |
| CF-15 | Stage track is a hard-coded array, not data-driven by application type. | APH paths differ by type (self-disclosure vs EVC vs SHC vs closure). | §2 Table 2.3; §3.2 | M |
| CF-16 | No letter/notice history, dispatch acknowledgement or public-publication status. | APH requires portal publication and download of decisions/letters. | 1.10; 2.25k | M |
| CF-17 | No audit panel scoped to the case. | A case reviewer cannot see the full who/what/before/after history without leaving the case. | Project audit requirement; 1.10 | S |
| CF-18 | No "next required action / owner / deadline" panel driven by APH clocks. | The sidebar shows generic SLA and actions, not the statutory next step. | §5; 1.8-1.12 | M |

### 9.3 Missing case-file capabilities

| ID | Missing capability | Minimum useful slice | Effort |
|---|---|---|---|
| CF-M1 | APH stage track | Data-driven stages for new/existing/self-disclosure paths. | M |
| CF-M2 | Decision/letter tab | LoA/LoD/LoR, Speaking Order, issue date, download, acknowledgement. | L |
| CF-M3 | Appeal panel | File appeal, 7-day countdown, SAC hearing, outcome, send-back loop. | L |
| CF-M4 | Deposit panel | Intimation, 15-day clock, proof, penalty status, release. | L |
| CF-M5 | Committee/hearing panel | Composition, quorum, attendance, COI, minutes, outcome. | L |
| CF-M6 | EVC evidence panel | Team, checklist, video URL, GPS, photos, report. | L |
| CF-M7 | Deficiency Report panel | Official report, item responses, re-scrutiny status. | M |
| CF-M8 | Payment/refund panel | TER, receipt, refund eligibility/calculation. | L |
| CF-M9 | Complaint/penalty panel | PGRC/SCSC, show-cause, hearing, penalty. | L |
| CF-M10 | Post-approval panel | Approved intake, enrolment, annual compliance, penalties. | L |
| CF-M11 | Case audit panel | Filtered audit trail with before/after diff. | S |
| CF-M12 | Next-action panel | Clause, owner, due date, consequence. | M |

### 9.4 Case-file verdict

The case file is the **best demonstration surface** in the product and the place where APH gaps will be most visible to judges. It currently tells a coherent generic story, but not the AICTE story. A four-day improvement should prioritize the **stage track, decision/letter tab, appeal timer and deposit panel**; committee/hearing and post-approval panels can be read-only mock records if time is short.

---

## 10. APH alignment map

This section maps **every current role, application status, workflow stage and workflow action** to an APH-aligned replacement using APH §1 and §3. A replacement may split one current value into several APH concepts. "Remove" means there is no APH equivalent and the value should not survive in the target model.

### 10.1 Roles

| Current role | Current powers in code | APH actor(s) and duty | APH-aligned replacement | APH reference | Effort |
|---|---|---|---|---|---|
| `INSTITUTION_ADMIN` | Create/edit/submit/withdraw own institution's application; respond to deficiencies; upload documents. | Applicant institution; submits online, pays TER, uploads documents, responds to deficiencies, appeals. Two authorised representatives attend Scrutiny/SHC/SAC. | Keep `INSTITUTION_ADMIN` as the institution account, add `INSTITUTION_REPRESENTATIVE` records for the two authorised attendees. Scope remains institution-only. | §1; 1.4.1-1.4.5; 1.8c; 1.11d; 2.24e | M |
| `SCRUTINY_OFFICER` | Verifies documents, starts scrutiny, raises/closes deficiencies, schedules inspection; can read all cases in region. | Regulation Bureau schedules committees, informs institutions, puts observations before committees and issues letters. Scrutiny/Re-Scrutiny Committee verifies document authenticity. | Split into `REGULATION_BUREAU_OFFICER` (intake, scheduling, observations, letters) and `SCRUTINY_COMMITTEE_MEMBER` (document verification, scrutiny/re-scrutiny, deficiency report). Remove region-wide read from committee members. | §1; 1.8a; 1.10; Annexure-16 (16.3-16.4) | L |
| `INSPECTION_COMMITTEE` | One user is assigned to a visit and submits a free-form report/recommendation. | Expert Visit Committee: multi-member team with prescribed composition, automated selection, conflict rules, online/physical verification and a report. | Replace with `EVC_MEMBER` plus `evc_visits`/`evc_members` membership. A user can be a member of multiple visits; the visit has a chair, quorum and checklist. | §1; 1.9a-f; Annexure-16 (16.5) | L |
| `REGIONAL_HEAD` | Starts scrutiny, assigns officers, sends to committee, approves, conditionally approves, rejects; reads region compliance/audit. | Regional Office/Regional Officer constitutes the EVC. The Executive Committee takes the approval decision; Council ratifies. Regional Committee endorses LoA/LoR. | Replace with `REGIONAL_OFFICER` (constitute/schedule EVC; regional oversight) and `EXECUTIVE_COMMITTEE_MEMBER` (decision). Record Regional Committee endorsement as a workflow step, not a super-role. Remove decision powers from the regional role. | §1; Definitions 29; 1.10a; Annexure-7 | L |
| `SUPER_ADMIN` | Member of every workflow transition; can perform every action; administers compliance/alert rules and audit. | APH role map uses `SUPER_ADMIN` for the Council secretariat. Platform administration is not an adjudicative role. | Keep `SUPER_ADMIN` for platform/master-data administration and Council secretariat support. Remove it from all operational transitions. Council ratification is a separate action performed by `SUPER_ADMIN` in the Council-secretariat capacity, requiring a recorded EC recommendation and ratification record; it is not a bypass. | §1; 1.10a; 2.25a | M |

**Roles with no current equivalent that must be added:** `REGULATION_BUREAU_OFFICER`, `SCRUTINY_COMMITTEE_MEMBER`, `EVC_MEMBER`, `REGIONAL_OFFICER`, `SHC_MEMBER`, `SAC_MEMBER`, `EXECUTIVE_COMMITTEE_MEMBER`, `COMPLAINT_SCRUTINY_MEMBER` (SCSC). `SUPER_ADMIN` remains for Council secretariat/platform administration.

### 10.2 Application statuses

| Current status | Current meaning | APH-aligned replacement | APH reference | Effort |
|---|---|---|---|---|
| `DRAFT` | Editable application not yet submitted. | Keep `DRAFT`; editable until final submission, then immutable. | 1.4.3 | S |
| `SUBMITTED` | Submitted, before assignment. | `SUBMITTED` only after TER payment, DSC, Affidavit 2 and State/university copy acknowledgement; otherwise `PAYMENT_PENDING`/`DRAFT`. | 1.4.2e-f; 1.4.3; 1.4.5 | M |
| `DOCUMENT_VERIFICATION` | One officer verifies uploaded documents before scrutiny. | Remove as a separate status; fold document authenticity verification into `SCRUTINY` by the Scrutiny Committee. | 1.8; Annexure-1/2 | M |
| `SCRUTINY` | Scrutiny stage. | Keep `SCRUTINY`; add `RE_SCRUTINY` for the deficiency-only re-check. | 1.8; §3.1 step 4 | M |
| `DEFICIENCY_RAISED` | Ad-hoc deficiencies issued. | `DEFICIENCY_REPORT_ISSUED` (official Deficiency Report) with a response deadline and re-scrutiny path. | 2.3.3b; 2.4; 1.8 | M |
| `DEFICIENCY_RESPONDED` | Institution has answered all deficiencies. | `DEFICIENCY_RESPONDED` then `RE_SCRUTINY`; re-scrutiny verifies only the listed deficiencies. | 1.8; 2.4 | M |
| `INSPECTION_SCHEDULED` | One inspection committee member scheduled. | `EVC_SCHEDULED` with a constituted multi-member EVC, visit mode and checklist. | 1.9a-f; Annexure-16 (16.5) | L |
| `INSPECTION_DONE` | One member submitted a report. | `EVC_REPORT_SUBMITTED`; report goes to EC (or SHC where applicable). | 1.9; §3.1 step 5; 2.23.3 | M |
| `COMMITTEE_REVIEW` | Generic committee review before decision. | Split into `SHC_REVIEW` (existing-institution compliance/complaints, where applicable) and `EC_REVIEW` (decision agenda). | 2.23.3; 7.10; 1.10a | L |
| `APPROVED` | Terminal approval status. | Split into `EC_RECOMMENDED` → `COUNCIL_RATIFIED` (LoA cases) → `LOA_ISSUED`; then `SECURITY_DEPOSIT_PENDING` → `CLOSED`. | 1.10a; 1.12; 2.25f | L |
| `CONDITIONALLY_APPROVED` | Terminal conditional approval with free-text conditions. | Remove. APH does not normally allow conditional/partial approval. Use `LOA_ISSUED` with post-approval compliance conditions, or `LOD_ISSUED`/`LOR_ISSUED` where the case fails. | 4.9c; 2.27; 4.4.3 note | M |
| `REJECTED` | Terminal rejection with a comment. | Replace with `LOD_ISSUED` or `LOR_ISSUED`, each with a Speaking Order and a 7-day appeal window; `APPEAL_FILED` → `SAC_REVIEW` → `COUNCIL_FINAL`. | 1.10; 1.11a-e; 2.24a | L |

**Overlay:** `is_withdrawn` should become a real `WITHDRAWN`/`REVOKED` state with APH timing and refund rules, not a flag that leaves the old status intact. `is_escalated` can remain a derived monitoring flag, but it is not an APH status.

### 10.3 Workflow stages

| Current stage | Current use | APH-aligned replacement | APH reference | Effort |
|---|---|---|---|---|
| `APPLICATION` | Draft/submitted. | `APPLICATION` / `PRE_SUBMISSION`. | 1.4 | S |
| `DOCUMENT_VERIFICATION` | Officer verification. | Fold into `SCRUTINY`. | 1.8 | M |
| `SCRUTINY` | Scrutiny and post-deficiency return. | `SCRUTINY` / `RE_SCRUTINY`. | 1.8 | M |
| `DEFICIENCY` | Deficiency response. | `DEFICIENCY` / `RE_SCRUTINY`. | 2.3.3b; 2.4 | M |
| `INSPECTION` | Single-member inspection. | `EVC` (schedule, visit, report). | 1.9 | L |
| `COMMITTEE_REVIEW` | Generic review. | `SHC` and `EC` as separate stages; complaints add `SCSC`. | 2.23.3; 7.10; 1.10a | L |
| `DECISION` | Declared and configured but never used. | `EC_DECISION`, `COUNCIL_RATIFICATION`, `APPEAL/SAC`; or remove until implemented. | 1.10a; 1.11e; 2.24a | M |
| `COMPLETED` | Terminal. | `LETTER_ISSUED` (LoA/LoD/LoR), then `SECURITY_DEPOSIT`/`CLOSED`; appeal can reopen. | 1.10; 1.11; 1.12 | L |

### 10.4 Workflow actions

| Current action | Current actor | APH-aligned replacement | APH reference | Effort |
|---|---|---|---|---|
| `submit` | Institution admin | Keep `submit`, but gate on TER, DSC, Affidavit 2 and State/university copy. | 1.4.2e-f; 1.4.3; 1.4.5 | M |
| `auto_assign` | Regional head / super admin | `schedule_scrutiny_committee` by Regulation Bureau, using automated committee selection. | 1.8a; Annexure-16 (16.3-16.4) | L |
| `verify_documents` | Scrutiny officer | `scrutiny_verification` by the Scrutiny Committee; no separate officer step. | 1.8; Annexure-1/2 | M |
| `start_scrutiny` | Regional head | `convene_scrutiny` by Regulation Bureau; committee members selected by portal process. | 1.8a | M |
| `raise_deficiency` | Scrutiny officer | `issue_deficiency_report` by Scrutiny/Re-Scrutiny/SHC/EVC, with item-level observations. | 2.3.3b; 2.4; 1.8 | M |
| `respond_deficiency` | Institution admin | Keep `respond_deficiency`; add evidence and authorised-representative attestation. | 1.8c; 2.4 | M |
| `close_deficiency` | Scrutiny officer | `re_scrutiny` / `accept_compliance`; verify only the listed deficiencies. | 1.8; 2.4 | M |
| `schedule_inspection` | Scrutiny officer / regional head | `constitute_evc` + `schedule_evc` by Regional Officer, with composition/quorum/COI checks. | 1.9a; Definitions 29; Annexure-16 (16.5) | L |
| `submit_inspection_report` | Inspection committee | `submit_evc_report` by the EVC chair after quorum; attach checklist, video, GPS and evidence. | 1.9a-g | L |
| `send_to_committee` | Regional head | `refer_to_shc` (where applicable) or `refer_to_ec`; Regulation Bureau places observations before the committee. | 2.23.3; 1.10a; §3.1 step 6 | M |
| `approve` | Regional head / super admin | Split into `ec_decision` → `council_ratification` → `issue_loa`; no single actor. | 1.10a; 2.25a | L |
| `conditionally_approve` | Regional head / super admin | Remove. No conditional/partial approval; use LoA with post-approval conditions or LoD/LoR. | 4.9c; 2.27 | M |
| `reject` | Regional head / super admin | Split into `ec_decision` → `issue_lod`/`issue_lor` with Speaking Order and appeal clock. | 1.10; 1.11a; 2.24a | L |
| `withdraw` | Institution admin | `withdraw_application`/`revoke_application` with 7-day/10-April windows and refund calculation; `withdraw_closure` by 10 April. | 2.3.3f-g; 1.4.2h | L |

### 10.5 APH states/actions with no current equivalent

| APH concept | Why it is missing today | Effort |
|---|---|---|
| `RE_SCRUTINY` | No deficiency-only re-check. | M |
| `EVC_SCHEDULED`, `EVC_REPORT_SUBMITTED` | Single-member inspection only. | L |
| `SHC_REVIEW` | No hearing body. | L |
| `EC_REVIEW`, `COUNCIL_RATIFICATION` | Decision made by regional head. | L |
| `LOA_ISSUED`, `LOD_ISSUED`, `LOR_ISSUED` | No letter objects. | L |
| `APPEAL_FILED`, `SAC_REVIEW`, `COUNCIL_FINAL` | No appeal route. | L |
| `SECURITY_DEPOSIT_PENDING`, `DEPOSIT_RELEASED`, `DEPOSIT_FORFEITED` | No deposit lifecycle. | L |
| `COMPLAINT_FILED`, `PGRC_REVIEW`, `SCSC_REVIEW`, `SHOW_CAUSE`, `PENAL_ACTION` | No complaint/penalty module. | L |
| `RESTORATION`, `CLOSURE`, `HIBERNATION`, `CHANGE_OF_SITE` | No type-specific tracks. | L |
| `EXTENDED_EOA_ELIGIBLE`, `SELF_DISCLOSURE_EOA` | No eligibility/self-disclosure path. | L |

### 10.6 Mapping verdict

The mapping shows the core problem clearly: **one private workflow is being asked to carry a multi-body statutory process**. The target model should keep the state-machine pattern but make the vocabulary, actors and letters APH-native. The first three mappings (roles, statuses, actions) are the minimum for a credible demo; the stage mapping follows from them.

---

## 11. Ambiguities and assumptions

The APH extract itself flags ambiguities in §12. They must be **configurable**, not guessed in code.

| ID | Ambiguity in APH_SPEC §12 | Product handling |
|---|---|---|
| A-01 | Core-branch reduction: 2.6g allows up to 50% of approved intake (not below 30); 2.18a says up to 30 seats. | Store the limit as a per-type, per-level rule with a clause reference; do not hard-code either value. Show the conflict in the admin screen. |
| A-02 | Appeal clock: 1.11a counts 7 days from LoD issue; 2.24a counts from decision upload. | Make the start event (`issued_at` vs `uploaded_at`) a configurable field on the appeal deadline. |
| A-03 | Cross-references to missing clauses (e.g. Annexure-2.1(iii) "7.17", Annexure-3 3.2f "Chapter VII", 2.18b "Annexure 6/7", 2.13.1 "2.10.2(b)"). | Store clause text as data; do not invent the missing clause. Flag as "reference unresolved" in the admin UI. |
| A-04 | Security Deposit term: text says 10 years; Affidavit 6 says 8/10 years. | Make the term a configuration value; default to 10 years with an explicit note. |
| A-05 | Table 1.3 divisions "6/12" for E&T. | Interpret as 6 divisions of 60 or 12 divisions of 30; keep both parameters configurable. |
| A-06 | Dates tied to AY 2024-25 (NBA validity 30 Apr 2025, NIRF 8th edition, QS Asia 2024, previous LoR year 2023-24). | Store a "reference year" parameter per criterion; never bake the example year into logic. |
| A-07 | Course lists contain duplicates and spelling variants. | Normalise during seeding and keep a source-row reference for traceability. |
| A-08 | Table 2.3 shows "–" under Self-Disclosure for types that other clauses require to have "Nil Deficiency based on Self-Disclosure". | Generate a Deficiency Report for every type; do not use the dash to suppress it. |
| A-09 | PG cadre ratio: R = 3 for PG E&T/HMCT, R = 9 for MCA/MBA/PGDM, unmarked for PG Planning/Applied Arts/Design. | Make R configurable per programme and level; show "unresolved" for the unmarked rows. |
| A-10 | Scrutiny described as presenting originals, while online mode is the norm and recordings are made for transparency. | Make scrutiny mode (online/physical/hybrid) and recording requirement configurable per committee/type. |

### Assumptions used in this report

1. `docs/reference/APH_SPEC.md` is the authoritative source for this audit. Clause numbers are quoted as they appear in that extract.
2. Effort estimates assume one experienced full-stack developer familiar with this repository, not a team working in parallel.
3. "Four days" means four working days, not 96 continuous hours.
4. No real AICTE data is used; all seeded institutions and thresholds remain fictional/illustrative.
5. A "minimum useful slice" means a real database record and API/UI path, not a hard-coded demo string.

---

## 12. Evidence, coverage and limitations

### 12.1 What was inspected

| Area | Evidence |
|---|---|
| Project rules | `AGENTS.md` read in full |
| APH source | `docs/reference/APH_SPEC.md` read in full |
| Database | `backend/app/models/*.py`; Alembic migrations `0001`-`0007` |
| Roles/RBAC | `enums.py`, `api/dependencies.py`, `services/authorization.py`, `services/workflow.py`, seed accounts |
| Application portal | `api/routes/application_workspace.py`, `services/application_workspace.py`, `services/application_sections.py`, schemas, wizard UI |
| Workflow | `services/workflow.py`, `api/routes/workflow.py`, workflow schemas, `test_workflow.py` |
| Compliance | `services/compliance.py`, `compliance_admin.py`, seed rules, compliance UI |
| Alerts | `services/alert_engine.py`, `services/scheduler.py`, alert routes, alert UI |
| UI | `App.tsx`, `AppLayout.tsx`, `lib/roles.ts`, all pages, case-file components |
| Tests | 16 backend test modules under `backend/tests/` |

### 12.2 Inventory counts

| Item | Current count |
|---|---|
| Database tables | 17 |
| Roles | 5 |
| Application types creatable through API | 2 (`NEW`, `EXTENSION`); 3 enum values |
| Application statuses | 12 |
| Workflow stages | 8 |
| Workflow actions | 14 |
| APH application types in §2 | 21 + Chapter I/university/ODL/collaboration variants |
| Seeded compliance rules | 15 |
| Seeded alert rules | 11 |
| Alert trigger types | 8 |
| Backend test modules | 16 |

### 12.3 Verification statement

This was a **documentation-only** step:

- No backend, frontend, migration, seed, test, Docker or Makefile file was modified.
- `docs/GAP_REPORT.md` was created.
- `docs/reference/APH_SPEC.md` was created earlier in the same audit from the supplied specification.
- No tests were run as part of this step because no code changed. The repository's prior test/build status is not re-verified here.
- The repository is not a Git repository, so change verification was done by file inspection rather than `git diff`.

### 12.4 Limitations

1. The APH source is the supplied extract, not the full 231-page PDF. Some clause details may be abbreviated in the extract; all citations are therefore traceable to `APH_SPEC.md`, not independently re-read from the PDF.
2. The audit covers the MVP scope in `AGENTS.md` (one deep New/Extension flow). It does not attempt to specify every Chapter III/IV/V workflow in implementation detail.
3. Effort estimates are planning estimates, not commitments.
4. The current compliance and alert thresholds are explicitly illustrative; this report does not certify any of them as AICTE norms.
5. UI findings are based on source inspection, not a fresh browser walkthrough of every role in this step.

---

## 13. Top 10 highest-value fixes for a four-day deadline

Ordered by dependency and demo value. The first seven are the realistic four-day core; items 8-10 are stretch work if the core lands early. **Do not attempt all 21 application types or the full Annexure-3/4/5 calculators in four days.**

| # | Fix | Why it is high value | Concrete four-day scope | Effort | Suggested day |
|---|---|---|---|---|---|
| 1 | **Remove the integrity contradictions** | `SUPER_ADMIN` can currently approve, `REGIONAL_HEAD` decides, and `CONDITIONALLY_APPROVED` is a valid outcome. These are the easiest findings for a judge to challenge. | Remove `SUPER_ADMIN` from operational transitions; remove `conditionally_approve`/`CONDITIONALLY_APPROVED`; relabel `REGIONAL_HEAD` as `REGIONAL_OFFICER` with no decision action; add a test proving platform admin cannot decide. | S/M | Day 1, first 2 hours |
| 2 | **Replace the workflow vocabulary and core path** | Everything else (UI, alerts, letters, audit) depends on APH-native states/actions. | Add `RE_SCRUTINY`, `EVC_SCHEDULED`, `EVC_REPORT_SUBMITTED`, `SHC_REVIEW`, `EC_REVIEW`, `COUNCIL_RATIFICATION`, `LOA_ISSUED`, `LOD_ISSUED`, `LOR_ISSUED`, `APPEAL_FILED`, `SAC_REVIEW`; rewrite `TRANSITIONS`; keep the single state machine. Seed one happy path and one deficiency path. | L | Days 1-2 |
| 3 | **Add decision letters and the 7-day appeal** | The legal output is the point of the process; a status badge is not an approval. | `decisions` + `decision_letters` tables; LoA/LoD/LoR templates; Speaking Order field; issue/publish/download; 7-day appeal timer with configurable start event; SAC placeholder hearing. | M/L | Day 2 |
| 4 | **Gate submission on TER, DSC and Affidavit 2** | APH says unpaid/unsigned applications are not considered. This is a visible, high-credibility gate. | Fee rule table with a small NEW/EXTENSION slice; compute TER; payment record; DSC flag; Affidavit 2 upload; block `submit` with clear missing-item messages. | M | Day 2 |
| 5 | **Add minimal committee and EC/Council records** | Without a committee, EC and Council, the new workflow is only renamed statuses. | `committees`, `committee_members`, `committee_meetings`, `decisions`, `council_ratifications`; composition/quorum/COI fields; seed one scrutiny committee, one EVC and one EC; record attendance and decision. | L | Days 2-3 |
| 6 | **Rebuild the case-file stage track and decision panel** | The case file is the main demo surface; it must show the APH path and the letter. | Data-driven stage track; Decision tab with LoA/LoD/LoR, Speaking Order and appeal countdown; replace "Regional head" action ownership; add a "next action/owner/deadline" panel. | M | Day 3 |
| 7 | **Add two real compliance calculators and the essential-requirements checklist** | Demonstrates APH-specific compliance instead of generic thresholds. | Faculty FSR calculator (S, ratio, cadre 1:2:6, 25% reduction, adjunct cap) and built-up-area calculator (instructional + admin + amenities + 25% circulation); 6.47-6.53 yes/no checklist with evidence. Keep the existing RAG as a summary. | L | Days 3-4 |
| 8 | **Add the statutory deadline catalogue and alerts** | Reuses the strongest subsystem and makes the 7/15-day clocks visible. | Event-driven deadlines for appeal (7 days), Security Deposit (15 days + 10%/20%), enrolment (30 Nov), IC report (30 June), monthly complaint report; replace the hard-coded trigger `CHECK` with a trigger table. | M | Day 4 |
| 9 | **Add the application-type router and one self-disclosure path** | Shows APH breadth without pretending to implement 21 types. | Type catalogue seeded from §2; route `NEW`, `EXTENSION` and one existing-institution self-disclosure flow; type-driven document checklist; explicit "not yet implemented" for the rest. | M | Day 4 |
| 10 | **Add the Security Deposit lifecycle** | Highly APH-specific and visually compelling; completes the LoA story. | Intimation, 15-day timer, Affidavit 3/proof, 10%/20% penalty ladder, release checklist (PGRC/vigilance/FDR NOC), forfeiture flag; case-file panel. | M/L | Day 4 stretch |

### 13.1 If only one day is available

Do **1, 2 (happy path only), 3 (LoA/LoD only) and 6 (stage track + decision panel)**. That produces a coherent APH-shaped demo: a case moves through scrutiny → EVC → EC → Council → letter, with a visible appeal clock and no false conditional approval.

### 13.2 What not to fake

- Do not label generic thresholds as AICTE norms.
- Do not claim all 21 application types are supported.
- Do not show an EC/Council decision that no committee record supports.
- Do not show a LoA without a decision, ratification and letter record.
- Do not claim compliance with 6.47-6.53 from a URL-presence check.
- Do not claim a Security Deposit is compliant without the 15-day clock and proof.

### 13.3 Definition of done for the four-day slice

A reviewer can, through the UI and API:

1. Log in as the institution and submit a **paid, DSC-signed, Affidavit-2-backed** New/Extension application.
2. See it scheduled to a **Scrutiny Committee**, receive a Deficiency Report, respond, and watch **Re-Scrutiny** clear only the listed items.
3. See an **EVC** visit with a multi-member team and a report.
4. See an **EC** decision and **Council ratification**.
5. Download an **LoA/LoD/LoR** with a Speaking Order.
6. See a **7-day appeal** clock and an **SAC** placeholder.
7. See the full path on the case-file stage track and in the audit log.
8. See at least one real APH compliance calculation (FSR or built-up area) and the essential-requirements checklist.

That is a credible APH prototype. The remaining gaps are then an honest, documented roadmap rather than hidden non-compliance.

---

*End of report.*
