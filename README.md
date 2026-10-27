# Integrated AICTE Approval Workflow Automation, Compliance Monitoring and Alert Management System

A Smart India Hackathon prototype that digitises the AICTE approval cycle for technical
institutions and continuously monitors compliance against configurable norms. The MVP covers
**one deep flow**: New/Extension of Approval for an Engineering/Management institution.

> **Data disclaimer:** This repository contains no real AICTE data. All sample institutions are
> clearly fictional. Compliance thresholds and SLA values are **illustrative** and must remain
> editable by administrators. They must be verified against the current AICTE Approval Process
> Handbook before any real use.
>
> The APH 2024-27 schema and role retrofit is documented in `docs/er-diagram.md`. Domain points
> that still need a handbook check or an administrative decision are tracked in
> `docs/OPEN_QUESTIONS.md`.

## Status

Implemented:

- Monorepo, Docker Compose development stack, PostgreSQL schema and Alembic migration
- FastAPI application factory, structured JSON logs, CORS, health and readiness probes
- JWT authentication with eight-hour access tokens and bcrypt password hashing
- Role-based API access with institution, assignment and region scoping
- Audit service, login auditing and a restricted, filterable audit-log API
- Role-scoped application read endpoints for the demo flow
- Institution-side draft workspace: create/update/delete drafts, JSONB section data,
  programme CRUD and a multi-step wizard
- Database-driven required-document checklists with authenticated, versioned PDF/JPG/PNG uploads
- Completeness validation that blocks incomplete submissions with field and document-level errors
- Submission that records a workflow event, audit entry, submitted timestamp and an illustrative
  SLA due date from `SLAConfig`
- Role-scoped global search across applications, institutions and permitted pages
- An authenticated application shell with responsive role navigation, command palette,
  keyboard shortcuts, an unread-count notification bell and a filterable alert inbox
- A database-driven alert and escalation engine with eight trigger types, in-app/email/mock-SMS
  delivery, template rendering, dedupe keys and a 15-minute APScheduler scan
- Officer → Regional Officer → Super Admin escalation with severity raising, application escalation
  state, workflow events and acknowledge-to-stop semantics
- Alert inbox filters and acknowledgement, plus a `/alert-rules` admin screen for `SUPER_ADMIN`
- A single workflow state machine for submission, document verification, scrutiny, deficiency
  raise/respond/close, inspection scheduling and reporting, committee review and decision
- Database-driven compliance rules with a safe comparison evaluator, metric extraction, weighted
  0–100 scores, per-rule explanations, missing-data handling and RED/AMBER/GREEN status
- Continuous compliance monitoring: nightly APScheduler evaluation, re-evaluation on application
  writes and an on-demand admin run, with append-only institution snapshots for trend charts
- Compliance admin APIs and a `/compliance` screen for `SUPER_ADMIN` and `REGIONAL_OFFICER`:
  rule list/add/edit/activate, threshold impact preview, editable severity weights and RAG bounds
- APH calculator engine with a clause-cited rule library: faculty establishment and the 1:2:6 cadre
  split, instructional and built-up area, library, students-per-computer and bandwidth tiers, and
  land/lease checks — all seeded as data with admin-editable norms
- Nil Deficiency decided by mandatory rules only, with illustrative project thresholds clearly
  badged, APH 7.3 penal-action suggestions for APH 7.4 violations, and a downloadable Deficiency
  Report PDF
- A compliance tab on the application detail page with rule-by-rule pass/fail, severity badges,
  score gauge and human-readable explanations
- DEBUG-only simulated clock for demonstrating deadline, SLA breach and escalation behaviour in
  seconds, including a day-by-day scheduler replay
- React login, protected routing, role-specific navigation and account overview
- A token-driven frontend design system with a public `/dev/ui` showcase
- Pytest coverage for login, token claims, role denial, tenant isolation, audit filtering,
  global search, alert recipient scoping, alert dedupe, each trigger firing once, escalation
  chains, acknowledgement stopping escalation, admin rule CRUD, application filters, simulated
  time, draft ownership, programme CRUD, document versioning, completeness rules, blocked
  submission, workflow transitions, compliance operators/scoring/missing data, monitoring
  snapshots, rule impact and admin rule edits that change live outcomes

Remaining out of scope for this MVP increment: executive dashboards beyond the overview and
ML risk scoring. The SMS channel is intentionally a logging mock behind the
`NotificationProvider` interface; email uses a plain SMTP relay (Mailpit in development) without
a durable retry queue.

## Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, PostgreSQL
- **Frontend:** React, Vite, TypeScript, Tailwind CSS, Recharts, React Router, TanStack Query
- **Jobs:** APScheduler in-process nightly compliance monitoring (no Redis or Celery)
- **ML:** scikit-learn + joblib (introduced with risk scoring)
- **Notifications:** in-app (DB), SMTP through Mailpit for demos, mocked SMS provider
- **Auth:** PyJWT access tokens (eight-hour expiry), bcrypt hashes and role-based access control

## Repository layout

```
.
├── backend/            FastAPI application, models, migrations, tests
├── frontend/           React + Vite application
├── docs/               Design documents, including the ER diagram
├── docker-compose.yml  PostgreSQL, Mailpit, backend, frontend
├── Makefile            Developer commands
└── .env.example        Configuration template
```

## Quick start

Prerequisites: Docker with the Compose plugin.

```bash
cp .env.example .env
make dev
```

Or run Compose directly (defaults are built in, so `.env` is optional):

```bash
docker compose up --build
```

| Service       | URL                              |
| ------------- | -------------------------------- |
| Frontend      | http://localhost:5173            |
| API docs      | http://localhost:8000/docs       |
| Health        | http://localhost:8000/health     |
| Readiness     | http://localhost:8000/health/ready |
| Mailpit       | http://localhost:8025            |

Migrations run automatically when the backend container starts.

## Cloud Deployment (AWS EC2)

The system is configured for cloud deployment on an AWS Free Tier `t3.micro` instance (Ubuntu 24.04 LTS).

### Architecture & Service Ports

The entire stack runs via Docker Compose on the remote instance:

| Service | Container Port | Host Port | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend** | `5173` | `5173` | React + Vite UI |
| **Backend** | `8000` | `8000` | FastAPI REST API & Swagger (`/docs`) |
| **Mailpit** | `8025` / `1025` | `8025` / `1025` | SMTP email inspector (web UI on `8025`) |
| **PostgreSQL** | `5432` | `5432` | PostgreSQL 16 database (volume-persisted) |

> **Security Group Inbound Rules:** In the AWS EC2 Management Console, open inbound TCP traffic for ports `22` (SSH), `5173` (Frontend), `8000` (Backend API), and `8025` (Mailpit).

### Server Prerequisites & Setup

1. **Storage & Swap (Essential for `t3.micro` / 1GB RAM):**
   Allocate a 20 GB root EBS volume upon launch. Create a 2GB swap space to ensure Node/Vite and Docker builds run smoothly without out-of-memory errors:
   ```bash
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

2. **Install Docker Engine & Compose:**
   ```bash
   sudo apt update && sudo apt install -y ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo usermod -aG docker $USER
   newgrp docker
   ```

3. **Deploy & Seed:**
   ```bash
   git clone https://github.com/TanayJalan/SIH_2026.git
   cd SIH_2026

   # Configure public IP for frontend API calls and backend CORS
   cat << 'EOF' > .env
   VITE_API_URL=http://<YOUR_EC2_PUBLIC_IP>:8000
   CORS_ORIGINS=http://<YOUR_EC2_PUBLIC_IP>:5173,http://localhost:5173
   DEBUG=true
   DEMO_MODE=true
   EOF

   # Start containers and run seed
   docker compose up -d --build
   docker compose exec backend python -m app.seed
   ```

### Real-Time Update Workflow (Zero Data Loss)

When changes are committed locally and pushed to GitHub:
```text
[Local Machine] git push ---> [GitHub] ---> git pull & docker compose up -d --build [AWS EC2]
```

To update the running deployment on EC2:
```bash
cd ~/SIH_2026
git pull origin main
docker compose up -d --build

# Idempotent: loads any new reference rows (workflow definitions, alert rules,
# fee tables, ...) without overwriting administrator edits.
docker compose exec backend python -m app.seed
```

The backend container runs `alembic upgrade head` on start, so migrations are applied
automatically. The seed is only needed when a release adds or changes reference data.

**Data Persistence:** PostgreSQL data is preserved inside the named Docker volume `postgres_data`. Rebuilding the containers updates the code while preserving all created applications, users, compliance evaluations, and audit logs.


### Demo data

```bash
make seed
```

The seed is idempotent. It creates two fictional institutions with APH institution profiles,
approved programmes, faculty rosters and admission history, one account per APH role, five
applications (including decided cases for the public average) and one inspection with audit
records. It also loads the APH application-type routing table, fee schedule, Security Deposit rate
table (Table 1.4), required-document checklist, committee compositions, demo public notices and
academic calendar events, plus the illustrative SLA configuration, the 90-row compliance rule
library, the calculator norms, alert rules and default severity weights and RED/AMBER/GREEN
breakpoints. Change both seed passwords before sharing any environment.

| Role | Email |
| ---- | ----- |
| `SUPER_ADMIN` | `admin@example.edu` |
| `INSTITUTION_ADMIN` | `institution@example.edu` |
| `INSTITUTION_ADMIN` (South) | `institution.south@example.edu` |
| `REGULATION_BUREAU_OFFICER` | `regulation@example.edu` |
| `SCRUTINY_COMMITTEE_MEMBER` | `scrutiny@example.edu` |
| `EVC_MEMBER` | `inspection@example.edu` |
| `REGIONAL_OFFICER` | `regional@example.edu` |
| `SHC_MEMBER` | `shc@example.edu` |
| `SAC_MEMBER` | `sac@example.edu` |
| `EXECUTIVE_COMMITTEE_MEMBER` | `ec@example.edu` |
| `COMPLAINT_SCRUTINY_MEMBER` | `complaints@example.edu` |

- `admin@example.edu` uses `SEED_ADMIN_PASSWORD` (default `ChangeMe123!`).
- All other demo accounts use `SEED_DEMO_PASSWORD` (default `ChangeMe123!`).

With `DEMO_MODE=true` (the Compose development default), the login screen lists one account per role
and fills the email and password when an entry is selected. No demo accounts are exposed when demo
mode is off.

The West demo application (`DEMO-WEST-2026-001`) is assigned to the Scrutiny Committee member and
has an inspection assigned to the EVC member. The South application
(`DEMO-SOUTH-2026-001`) is used to demonstrate cross-tenant denial. The approved
`DEMO-WEST-2026-002` case supplies the public average-days-to-decision figure. The open applications
receive illustrative SLA due dates so the overdue filter and demo clock can be exercised; these
dates are demo scaffolding, not AICTE policy.

The seeded document rules are illustrative: `NEW_INSTITUTION` and `EOA_SELF_DISCLOSURE` require
an affiliation certificate, building-plan approval, faculty details, financial statement, land
ownership document and mandatory disclosure document; the NAAC/NBA certificate is optional. APH
document codes and clause references are stored on each requirement. The application-stage SLA is
seeded as 30 days with escalation after 20 days. These are prototype values, not AICTE policy, and
can be edited directly in the `required_documents` and `sla_configs` tables until an admin
configuration screen is built. Every SLA row carries `apH_clause = 'DEMO'` and
`needs_verification = true` until a real processing calendar is supplied.

No alert rows are seeded. The alert-rule catalogue is seeded as editable configuration, including
T-7/T-3/T-1 deadlines, SLA breach, deficiency due/overdue, document expiry at 30/15 days,
compliance RED, status change and inspection scheduled. A dedicated pending case,
`DEMO-WEST-2026-003`, is due in seven days so the **Demo time** control can replay the complete
deadline → SLA breach → escalation sequence.

### Tests

```bash
make test
```

This applies migrations and runs the backend test suite in an isolated Compose one-off container.
Tests create uniquely named fictional records and remove them afterwards.

The frontend has one Playwright acceptance flow for the document re-upload cycle. It creates its
own case through the API, so the demo data does not need a case in Scrutiny:

```bash
cd frontend
npx playwright install chromium   # first run only
npm run test:e2e
```

The stack must be running (`make dev`) and the browser test targets `http://localhost:5173` and
`http://localhost:8000` by default; set `E2E_BASE_URL` / `E2E_API_URL` to point elsewhere.

### Useful commands

```bash
make migrate   # apply pending migrations to the running backend
make seed      # create or reuse demo records
make logs      # follow service logs
make shell     # shell inside the backend container
make down      # stop containers, keep the database volume
```

## Roles and access scope

All roles require a Bearer token from `POST /auth/login`.

| Role | Scope |
| ---- | ----- |
| `INSTITUTION_ADMIN` | Applications and institution data for their own institution only |
| `REGULATION_BUREAU_OFFICER` | Applications across regions, scrutiny/process actions and audit records |
| `SCRUTINY_COMMITTEE_MEMBER` | Applications assigned to them or from institutions in their region |
| `EVC_MEMBER` | Applications with an Expert Visit Committee inspection assigned to them |
| `REGIONAL_OFFICER` | Applications, audit records and compliance monitoring/rules for their region |
| `SHC_MEMBER` | Cases referred to the Standing Hearing Committee |
| `SAC_MEMBER` | Appeals referred to the Standing Appellate Committee |
| `EXECUTIVE_COMMITTEE_MEMBER` | Cases referred to the Executive Committee for decision |
| `COMPLAINT_SCRUTINY_MEMBER` | Complaints referred to the Standing Complaint Scrutiny Committee |
| `SUPER_ADMIN` | All applications, audit records and compliance monitoring/rules |

The frontend filters the sidebar by role, but the API performs the authoritative checks. Direct
requests to a forbidden route return HTTP `403`.

## Public API

- `GET /public/stats` — unauthenticated figures for the login screen:
  - applications in progress: submitted records that have not reached a terminal decision
  - average days to decision: mean time from `submitted_at` to the last update of approved or
    rejected applications (the model does not yet have a separate decision timestamp)
  - institutions needing attention: distinct institutions with at least one in-progress application
    past its SLA due date
  - `demo_mode` and, only when enabled, one seeded account per role for the login disclosure.

`DEMO_MODE` defaults to `false` in the application settings and is set to `true` in the Compose
development stack. The backend refuses to start with `DEMO_MODE=true` when
`ENVIRONMENT=production`, so seeded demo credentials cannot be published from a production
configuration.

## Authentication API

- `POST /auth/login` — accepts `{ "email": "...", "password": "..." }` and returns an access token,
  expiry in seconds and the authenticated user profile.
- `GET /auth/me` — returns the current profile. Requires `Authorization: Bearer <token>`.
- Token claims include `sub`, `role`, `institution_id`, `iat`, `exp` and token type.
- Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default `480`, eight hours).
- Every successful login writes an `auth.login` audit row. Failed attempts return `401` without
  revealing whether the email exists.

Set a strong `SECRET_KEY` in `.env` outside local development. The default value in
`.env.example` is development-only.

## Read APIs

- `GET /applications?page=1&page_size=20` — paginated, role-scoped applications.
- `GET /applications?overdue=true&institution_id=<uuid>` — optional overdue and institution filters.
  Overdue means an SLA due date is in the past and the application is not approved, rejected or
  withdrawn. Results are ordered by earliest SLA due date.
- `GET /applications/{id}` — one application; cross-tenant access returns `403`.
- `GET /search?q=<query>` — role-scoped command-palette search. It matches application references,
  application UUID fragments, institution names/AICTE IDs/states and permitted page labels. An
  empty query returns only the page catalogue. Results are capped per group.
- `GET /alerts?page=1&page_size=20&unread=true` — in-app alerts addressed to the authenticated
  user, newest first. Optional filters: `status`, `severity`, `type`, `application_id` and
  `channel` (defaults to `IN_APP`). `unread=true` includes `PENDING` and `SENT` alerts.
- `GET /alerts/summary` — totals plus unread counts by severity for the signed-in user.
- `POST /alerts/{id}/ack` — acknowledge one of the signed-in user's in-app alerts. Returns `404`
  for another user's alert. Acknowledgement stops the escalation chain.
- `GET|POST|PATCH|DELETE /alert-rules` — `SUPER_ADMIN` CRUD for database-configured alert rules.
  Every write is audited with a before/after snapshot.
- `GET /audit-logs` — restricted to `SUPER_ADMIN`, `REGIONAL_OFFICER` and `REGULATION_BUREAU_OFFICER`, with:
  - `entity_type`, `entity_id`
  - `actor_id`
  - `start_date`, `end_date` (inclusive UTC dates)
  - `page`, `page_size`

Regional audit scope is derived from entries performed by users in the region and entries whose
polymorphic entity is an institution, application or user in that region.

## Institution workspace API

Draft writes require `INSTITUTION_ADMIN` and the application must belong to the signed-in user's
institution. Checklist, programme-list and document-read endpoints use the normal role-scoped
application access rules. Every write is audited.

### Drafts and sections

- `POST /applications` — body `{ "application_type": "<APH type>", "academic_year": "2026-27" }`.
  The type must exist in the seeded `application_type_routes` table; `track` and `category` are
  derived from that route unless supplied.
  Creates a `DRAFT` for the signed-in institution and returns the full detail payload.
- `PATCH /applications/{id}` — body `{ "data": { ... } }`. Merges the supplied sections into the
  draft's JSONB `data`; omitted sections stay unchanged.
- `DELETE /applications/{id}` — deletes a draft, its programmes, document rows and stored files.
- `GET /applications/{id}` — detail response now includes `data` and `programs`.
- `GET /applications/{id}/checklist` — combined section/document readiness with `percentage`,
  `can_submit` and a readable `missing` list.
- `GET /applications/{id}/documents/checklist` — database-driven document rules with upload status.

The `data` object accepts these sections:

- `institution_profile`: `head_name`, `address_line1`, `address_line2`, `city`, `state`,
  `pin_code`, `contact_email`, `contact_phone`, `website`
- `infrastructure`: `land_area`, `built_up_area`, `labs`, `library`, `hostel`
- `faculty`: `total`, `professors`, `associate_professors`, `assistant_professors`,
  `student_faculty_ratio`, `phd_faculty_ratio`
- `finance`: `tuition_fee`, `development_fee`, `other_fees`, `balance`
- `accreditation`: `naac_grade`, `nba_status`, `last_validated_on`
- `mandatory_disclosure_url`

Draft section schemas are intentionally permissive so partial values can autosave. Required-field,
email, phone, PIN and URL checks that block submission live in the completeness service. The
`reference` and other display-only values in `data` are preserved on updates.

### Programmes

- `GET /applications/{id}/programs`
- `POST /applications/{id}/programs` — `program_name`, `level`, `intake`, `faculty_count`, `lab_count`
- `PATCH /applications/{id}/programs/{program_id}` — partial update
- `DELETE /applications/{id}/programs/{program_id}`

Programmes are recorded and shown in the workspace and review, but do not currently block
submission; the acceptance gate counts required section fields and mandatory documents.

### Documents

- `POST /applications/{id}/documents` — multipart form with `doc_type` and `file`.
- `GET /applications/{id}/documents` — every uploaded version for the application.
  `?only_to_recheck=true` is the Re-Scrutiny view: only rejected documents and
  replacements still awaiting verification (APH 1.8g).
- `GET /applications/{id}/documents/{document_id}/download` — authenticated file stream.
- `GET /applications/{id}/documents/{document_id}/versions` — every version with its
  uploader, review status and download URL.
- `POST /applications/{id}/documents/{document_id}/reject` — reviewer rejection with a
  reason code (`UNREADABLE`, `NO_DSC`, `EXPIRED`, `WRONG_DOCUMENT`, `NAME_MISMATCH`,
  `INCOMPLETE`, `OTHER`), a mandatory comment and the APH clause. It sets the document to
  `REJECTED`, opens or links a deficiency item, moves the case into the compliance
  window and notifies the institution (APH 1.8f, 2.3.3b).
- `POST /applications/{id}/documents/{document_id}/reupload` — institution replacement
  (multipart: `file`, `signed_with_dsc`, `signer_name`, `valid_until`). It creates version
  N+1, marks the old row `superseded_by`, resets verification to `PENDING`, marks the
  linked deficiency `RESPONDED`, notifies the reviewer and writes an audit and workflow
  event (APH 1.4.3, 1.8f, 2.4).
- `POST /applications/{id}/documents/{document_id}/verify` — reviewer confirmation of a
  replacement (APH 1.8g).

Uploads must be PDF, JPEG or PNG, no larger than 10 MB. The service verifies the file signature
rather than trusting the browser MIME type, and the `doc_type` must exist in the database checklist
for the application type. Files are stored under `STORAGE_DIR` (the Compose named volume
`backend_storage` mounted at `/storage`) as `<application_id>/<doc_type>/<uuid>.<ext>`. There is no
public file URL: every download passes through the authenticated API. Re-uploading a document type
creates the next version and a new audit row; earlier versions remain available in the file list.

#### Rejection and replacement (APH 1.8f, 1.8g, 2.4)

A submitted application is locked (APH 1.4.3), but the institution may replace a document a
reviewer rejected or flagged while the case is in `DEFICIENCY_COMMUNICATED`,
`INSTITUTION_COMPLIANCE`, `COMPLIANCE_WINDOW` or `RE_SCRUTINY`. In `DRAFT` any document can be
replaced. Every other attempt returns HTTP `409` with the reason, and the UI hides the button.

Replacements run the strict contract before anything is stored: a DSC attestation with the
signer's name, a non-expired `valid_until` for fire, occupancy and structural certificates, a
readable PDF (blank or image-only scans are refused through `pdfplumber`), the accepted file types
and the 10 MB limit. Per-field messages come back as
`{"detail": {"message": ..., "errors": {"file": ..., "valid_until": ...}}}` so the dialog can show
them inline. `MAX_REUPLOADS_PER_DOCUMENT` (default `5`, see OQ-53) caps replacements.

`submit_compliance` carries the `documents_reuploaded` guard, so compliance cannot be submitted
while any rejected document still awaits its replacement. The institution is notified when a
document is rejected and reminded before the deficiency due date; the reviewer is notified when a
replacement arrives.

### Submission

- `POST /applications/{id}/submit` — re-runs completeness checks, sets `submitted_at`, computes
  `sla_due_at` from the `APPLICATION` stage in `SLAConfig`, records a `DRAFT → SUBMITTED`
  `WorkflowEvent` and audit entry, then calls the workflow entry point.

An incomplete draft returns HTTP `422` with a readable payload:

```json
{
  "detail": {
    "message": "Application cannot be submitted yet. Complete the missing items.",
    "percentage": 81,
    "missing": [
      {
        "code": "document.AFFILIATION_CERTIFICATE",
        "section": "Documents",
        "message": "Upload the required document: Affiliation certificate."
      }
    ]
  }
}
```

Submitted applications are read-only in the institution workspace.

## Compliance engine

The engine is **data plus pure calculators**: no threshold, ratio or status band is hard-coded in
the evaluator, and every rule cites the APH clause it implements.

| Part | Location |
| ---- | -------- |
| Rule library (90 rows) | `backend/seeds/aph/compliance_rules.json` |
| Calculator norms and scoring config | `backend/seeds/aph/compliance_config.json` |
| Pure APH calculators | `backend/app/services/compliance_calculators.py` |
| Metric extraction, safe evaluator, scoring | `backend/app/services/compliance.py` |
| APH 7.4 → 7.3 penalty suggestions | `backend/app/services/penal_actions.py` |
| Deficiency Report and PDF | `backend/app/services/deficiency_report.py` |

`SUPER_ADMIN` and `REGIONAL_OFFICER` manage the rules at `/compliance` (**Monitoring**, **Rules**,
**Scoring** and **Norm calculators** tabs). Every rule and configuration edit is audited with its
before/after values.

> **Verification notice:** real-clause rules cite an `APH` clause from
> `docs/reference/APH_SPEC.md`. Rules seeded as `illustrative` are project-only demo thresholds:
> they are advisory, carry an “Illustrative, not an AICTE norm” badge and are flagged
> `needs_verification`. Every figure must still be checked against the current AICTE Approval
> Process Handbook before an approval decision relies on it. Ambiguous readings are listed in
> `docs/OPEN_QUESTIONS.md` (OQ-38 … OQ-50).

### Calculators (APH 6.14, 6.17, 6.19, Annexure-3, Annexure-4)

Calculators are pure functions with unit tests built from the worked examples in `APH_SPEC.md`:

| Calculator | Formula |
| ---------- | ------- |
| `faculty_requirement` | `S = approved intake × programme duration`; required faculty `= ceil(S / ratio)`; ratios `20` (E&T UG), `15` (E&T PG), `25` (Diploma). The Principal/Director is the first Professor post. |
| `cadre_split` | `1:2:6` (R = 9): Professors and Associate Professors round down, the remainder goes to Assistant Professors, so 12 posts → 1 / 2 / 9. |
| `cadre_compliance` | Upward substitution is allowed (a Professor may cover an Associate post), downward is not. |
| `instructional_area` | Classroom/tutorial/workshop formula from Annexure-3 3.2. |
| `required_built_up_area` | `(instructional + 750 administrative + 500 amenities) × 1.25 circulation`. |
| `library_requirement` | Titles (100 first year + 50 per later year), volumes, journals and reading-room seats. |
| `pc_requirement` | Students ÷ students-per-computer ratio, with a 20-PC floor and printers at 5%. |
| `bandwidth_requirement` | 100 / 300 / 500 / 1000 Mbps tiers by sanctioned intake. |
| `lease_compliance`, `plot_compliance` | 30-year lease, live lease ≥ longest course, at most three plots within 2 km. |
| `reduced_enrolment_trigger`, `excess_admission` | Five-year admission ledger checks (APH 6.12a, 7.4g). |

The numeric inputs above live in `area_norms`, `fsr_ratios`, `cadre_ratios`, `library_norms`,
`pc_ratios` and `bandwidth_tiers` rows of `compliance_config`, so the **Norm calculators** tab can
correct them without a code change.

Each rule cites the handbook clause that *states the norm* — Chapter VI (`6.11`–`6.54`) or an
Annexure — not the chapter that punishes a breach. Chapter VII (`7.1`–`7.13`) is penal action, so
only `7.4a`–`7.4n` (the violation codes behind the suggested actions) may appear as a rule clause;
a test fails the build if a rule cites `7.1`, `7.2` or `7.3`.

### Rules and operators

`ComplianceRule(metric_key, operator, threshold, threshold_max, severity, applies_to,
applies_to_family, applies_to_level, apH_clause, mandatory, illustrative, weight, unit,
explanation_template, metric_params, penalty_codes, is_active)`

Operators are `>=`, `<=`, `=`, `==`, `BETWEEN`, `EXISTS`, `>`, `<`, `!=` plus three safe aggregate
operators that read their operands from `metric_params` instead of evaluating code:

- `RATIO` — `numerator` ÷ `denominator`, for example faculty ÷ required establishment.
- `SUM` — sum of the `metrics` list.
- `COUNT` — number of `metrics` equal to `equals`.
- `DATE_NOT_EXPIRED` — compares a certificate validity date with the evaluation date.

No `eval()` is used. `BETWEEN` is inclusive and requires an upper bound. `applies_to` accepts APH
application types (for example `NEW_INSTITUTION`, `EOA_SELF_DISCLOSURE`, `INCREASE_INTAKE`),
programme levels (`UG`, `PG`) or `ALL`; `applies_to_family`/`applies_to_level` narrow a rule to one
programme family and level. A family/level-scoped metric with no matching programme group is
reported as **data missing**, never as the institution-wide value.

Severity is `CRITICAL`, `HIGH`, `MEDIUM` or `LOW`. An optional per-rule `weight` overrides the
severity weight (25 / 15 / 8 / 4). Status bands are RED below 70 and AMBER below 85. All are
editable in the admin UI.

### Nil Deficiency and scoring

- **Nil Deficiency requires every mandatory rule to pass or be assessed.** A failed mandatory rule
  or unassessed mandatory evidence blocks it, whatever the RAG score says.
- Illustrative rules are advisory: a failure is shown as an observation and never blocks a Nil
  Deficiency result.
- A mandatory failure forces RED; unassessed mandatory evidence forces at least AMBER; a failed
  `CRITICAL` rule also forces RED.
- The score is `earned weight / assessed weight × 100` over assessed rules only, so missing metrics
  neither inflate nor deflate it.
- The case file shows rule-by-rule `PASS` / `FAIL` / `NOT_ASSESSED` with the APH clause, the
  observed and required values, an explanation, the Nil Deficiency banner and the score gauge.
- Snapshots are append-only per institution and power the trend chart. Evaluation runs nightly
  through APScheduler, after application data writes and on demand from **Re-evaluate now**. Set
  `COMPLIANCE_MONITOR_HOUR` (0–23) or `COMPLIANCE_MONITOR_ENABLED=false` to change or disable it.
- The monitor evaluates the institution's most recent application **that carries programme rows
  and whose type is not marked `not_implemented` in `application_type_routes`** — the New/Extension
  case the norms apply to. A year-round request such as a change of site carries no programme
  detail, and a type the workflow refuses to process returns HTTP 503, so neither may decide a
  snapshot. It falls back to the latest programme application, then to the latest application.
- A worsening to RED creates in-app alerts for the Regional Officer and super administrator.

### Penalty suggestions (APH 7.4 → 7.3)

A rule may carry APH 7.4 violation codes (`7.4a` … `7.4n`). When it fails, the engine returns the
matching APH 7.3 penal actions as **suggestions** with `suggests_only = true` and
`hearing_required = true`. The engine never mutates an approval: a show-cause notice, hearing and
speaking order remain mandatory workflow steps.

### Deficiency Report and PDF

`GET /applications/{id}/deficiency-report` returns the structured report and
`GET /applications/{id}/deficiency-report.pdf` renders the same report with reportlab. The report
lists the failed and unassessed mandatory items with their clauses, marks illustrative observations
separately and prints the Nil Deficiency banner only when no mandatory item is open.

### Compliance APIs

All endpoints require `SUPER_ADMIN` or `REGIONAL_OFFICER`; Regional Officers only see institutions
in their region.

- `GET /compliance/rules` — paginated rule catalogue with `category`, `family`, `level`,
  `search`, `needs_verification`, `illustrative`, `mandatory` and `include_inactive` filters.
- `POST /compliance/rules` — create a rule.
- `PATCH /compliance/rules/{rule_id}` — edit any field except the immutable code.
- `GET /compliance/rules/{rule_id}/history` — audited change history (actor, timestamp,
  changed fields).
- `POST /compliance/rules/impact` — preview a proposed rule change. Returns projected RED/AMBER
  flips, improvements and affected institutions. This is read-only; nothing is persisted.
- `GET /compliance/metrics` — metric catalogue for the rule editor.
- `GET /compliance/monitor` — paginated latest snapshot per institution.
- `POST /compliance/monitor/run` — immediate re-evaluation for the caller's scope.
- `GET /compliance/institutions/{institution_id}/trend?limit=50` — chronological score history.
- `GET /compliance/config`, `PUT /compliance/config` — severity weights, RAG breakpoints and the
  calculator norms.

The application-level read endpoint remains `GET /applications/{id}/compliance`. It evaluates the
current rules live, so an admin threshold edit changes the displayed result immediately without a
code deployment or re-seed.

## Alerts and escalation

Alerts are produced by database-configured `alert_rules`, not by hard-coded conditions. The eight
trigger types and their seeded default thresholds are:

| Trigger | Fires when | Seeded windows |
| ------- | ---------- | -------------- |
| `DEADLINE_APPROACHING` | An application is close to its stage SLA due date | T-7, T-3, T-1 days |
| `SLA_BREACHED` | The stage SLA due date has passed without a transition | Immediate |
| `DEFICIENCY_DUE` | An open deficiency response is almost due | T-3 days |
| `DEFICIENCY_OVERDUE` | A deficiency response is past due | Immediate |
| `DOCUMENT_EXPIRING` | An uploaded document expires soon | 30, 15 days |
| `COMPLIANCE_RED` | An institution worsens to RED compliance status | Immediate |
| `APPLICATION_STATUS_CHANGED` | The workflow records a status transition | Immediate |
| `INSPECTION_SCHEDULED` | An inspection visit is created | Immediate |

Each rule stores its code, severity, `days_before` threshold, channel list, message template,
first escalation role and active flag. Every row is editable from `/alert-rules` by a
`SUPER_ADMIN`, and every write is audited with a before/after snapshot. Deactivating or deleting a
rule stops future evaluations but leaves delivered alerts intact. The seeded values are
**illustrative** and must be reviewed against the current AICTE Approval Process Handbook.

### Channels and templates

- `IN_APP` writes a row to the database inbox. It is always included.
- `EMAIL` sends SMTP mail through Mailpit in development (`http://localhost:8025`).
- `SMS` uses a mock `NotificationProvider` that logs the message instead of sending it.

All providers sit behind the `NotificationProvider` interface in
`backend/app/services/alert_engine.py`, so a real SMS gateway can replace the mock without touching
rule evaluation. Templates support `{institution}`, `{application_reference}`, `{application_id}`,
`{due_date}`, `{days_remaining}`, `{stage}`, `{status}`, `{from_status}`, `{document}`,
`{deficiency}`, `{inspection_date}`, `{score}`, `{failed_count}` and `{failed_critical_count}`.
Unknown placeholders remain visible rather than crashing a delivery.

### Scheduling and idempotency

APScheduler runs `run_alert_scan` every 15 minutes (`ALERT_SCAN_INTERVAL_MINUTES`) in addition to
the nightly compliance job. Each scan evaluates every active rule against applications, open
deficiencies and expiring documents. One logical notification produces one row per recipient and
channel, guarded by a unique `dedupe_key` of trigger + entity + threshold. Re-running a scan, or
replaying a simulated day twice, therefore cannot duplicate an alert.

### Escalation chain

1. The first alert goes to the configured recipient (for most rules, the Regional Officer).
2. If the in-app alert is still unacknowledged after the SLA's `escalation_after_days`, or the
   stage SLA is already breached, it escalates one step: officer → `REGIONAL_OFFICER` → `SUPER_ADMIN`.
3. Each escalation creates a new alert with severity raised one level (`LOW → MEDIUM → HIGH →
   CRITICAL`), links it to its parent, and records a `WorkflowEvent(action="escalate")`.
4. The application keeps its workflow status and gains `is_escalated=true`, shown as an
   **Escalated** badge in the application list and case file.
5. Acknowledging the in-app escalation alert stops the next chain step. Email and SMS rows are
   delivery receipts and never count as acknowledgement.

The alert inbox, unread counts and escalation use the `IN_APP` rows only; outbound rows can be
inspected with `?channel=EMAIL` or `?channel=SMS`.

### Demo: deadline → breach → escalation

The seed includes a fictional pending case, `DEMO-WEST-2026-003`, due in seven days. With
`DEBUG=true`:

1. Sign in as the Scrutiny Committee member or Regional Officer and open **Demo time** in the top bar.
2. Choose **Advance 7 days**. The backend walks the simulated clock forward one day at a time and
   scans after each step, producing the T-3/T-1 deadline alerts and then the SLA breach.
3. Choose **Advance 1 day** to cross the escalation window. A `REGIONAL_OFFICER` escalation alert
   appears with raised severity, and the demo case shows the **Escalated** badge.
4. Open **Alerts** to filter by severity/status, read the chain and acknowledge an alert. The bell
   in the top bar shows the unread count and the latest alerts. Mailpit at
   `http://localhost:8025` shows the corresponding email deliveries.

The same flow is available directly through `GET /dev/simulate-time?days=8` (or `POST
/dev/simulate-time` with `{"days": 8}`). Both routes are only registered when `DEBUG=true`, and
each call is audited. Resetting the clock does not delete alerts already created.

## Storage

Document files are not served from the frontend build or a static directory. Compose mounts the
named volume `backend_storage` at `/storage` and sets `STORAGE_DIR=/storage`; override
`STORAGE_DIR` if the backend runs outside Compose. The directory must be writable by the backend
process. The API resolves stored paths under that root and rejects path traversal.

## Frontend

The frontend provides:

- A split login screen with a live public-stats strip, reduced-motion-aware count-up figures,
  show/hide password, screen-reader error announcements and demo-account form filling when
  `DEMO_MODE` is enabled
- Session restoration from the stored access token and automatic redirect to login on `401`
- Protected routes and a role guard for audit logs
- An authenticated shell with a fixed 240px sidebar that collapses to a 64px icon rail; below
  1024px the navigation becomes a left drawer.
- A sticky top bar with global search, notification bell, role badge and account menu. Content is
  capped at 1280px and detail pages have breadcrumbs.
- Role-specific navigation with an active left ink bar, keyboard hints and a persisted collapsed
  state in `localStorage`.
- Overview, applications, application detail, alerts, profile and audit-log pages.
- An alert inbox with severity/status filters, an unread-only toggle, summary cards, pagination and
  one-click acknowledgement. Escalated alerts show their chain level, and escalated applications
  show an **Escalated** badge in lists and on the case file.
- A top-bar notification bell with a polling unread count and a recent-alerts dropdown.
- An alert-rule admin page at `/alert-rules` for `SUPER_ADMIN`: trigger filter, activate/deactivate,
  create/edit dialog, template and channel configuration, and delete confirmation.
- A compliance admin page at `/compliance` for `SUPER_ADMIN` and `REGIONAL_OFFICER` with monitoring
  status, institution trend chart, rule catalogue/editor, impact preview and scoring configuration.
- A compliance tab on the application detail page with the score gauge and rule-by-rule outcomes.
- An institution application workspace at `/applications/new` and
  `/applications/:applicationId/edit` with eight steps: profile, infrastructure, faculty,
  finance, accreditation, programmes, documents and review.
- Debounced autosave (700 ms) with a visible save state, inline field validation, programme
  add/edit/remove, drag-free document checklist uploads with progress, authenticated downloads and
  a live completeness sidebar.
- A submission review that shows the server's blocking field/document list and an SLA note.
- Application and audit lists that switch from desktop tables to stacked cards below 1400px, where
  all columns would no longer fit without internal horizontal scrolling.
- A command palette with role-scoped application/institution/page search, recent items and an
  **Open overdue applications** quick action.
- A visible session warning and a data disclaimer
- A design-system showcase at `/dev/ui`

### Shell, search and keyboard shortcuts

Press **Cmd+K** (macOS) or **Ctrl+K** (Windows/Linux) anywhere in the authenticated app to open
the command palette. Press **?** outside a form field for the in-app shortcut reference. Two-key
navigation sequences are:

| Sequence | Destination |
| -------- | ----------- |
| `g d` | Overview |
| `g a` | Role-specific applications list |
| `g c` | Compliance (Super Admin and Regional Officer only) |
| `g l` | Alerts |
| `g r` | Alert rules (Super Admin only) |
| `g u` | Audit logs (Super Admin, Regional Officer and Regulation Bureau only) |
| `g p` | Profile |

The palette searches application references, application ID fragments, institution names and
permitted pages. Selecting an institution opens the applications list filtered by that institution;
the overdue quick action opens the list filtered to past-SLA cases. Recently opened palette items
are stored locally per account.

### Demo time (DEBUG only)

The top-bar **Demo time** control appears only when the backend runs with `DEBUG=true`. It shows the
simulated date and offers **Advance 1 day**, **Advance 7 days** and **Reset to real time**. Advancing
does not merely move a display date: the backend replays the alert scheduler one day at a time, so
each intermediate T-7/T-3/T-1 window is evaluated before the final date. This is what produces the
deadline → SLA breach → escalation sequence in a few clicks. The clock is process-local, is audited
as `dev.time.advance` / `dev.time.reset` / `dev.time.simulate`, and resets when the backend reloads.
It changes overdue calculations without mutating stored SLA due dates.

To run the acceptance demo, open **Demo time → Advance 7 days**, then **Advance 1 day**, on the
seeded `DEMO-WEST-2026-003` case. The same result is available from the API:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/dev/simulate-time?days=8"
```

The response reports `alerts_created`, `escalations` and `notifications_sent`. Use `POST
/dev/simulate-time` with `{"reset": true}` to return to real time; created alerts and escalation
events are retained.

To enable the control locally:

```bash
# .env
DEBUG=true

docker compose up -d backend
```

Do not enable demo mode outside local development. The `/dev/simulate-time` routes are not
registered when `DEBUG=false`.

Run the frontend locally with:

```bash
cd frontend
npm install
npm run dev
```

### Design system

Open **http://localhost:5173/dev/ui** to review every foundation, component state and signature
view. The route is public and does not require a login.

- Colours, type, radii and elevation are declared once in `frontend/tailwind.config.ts` and
  `frontend/src/index.css`; components consume semantic utilities such as `bg-surface`,
  `text-ink-700` and `rounded-panel`, never raw hex values.
- IBM Plex Sans and Source Serif 4 are self-hosted through `@fontsource`. Numeric interfaces use
  tabular numerals by default.
- Reusable primitives and the `SlaRing`, `StageTrack` and `ScoreGauge` components live in
  `frontend/src/components/ui`.
- Copy rules, action labels, toast wording and error conventions are documented in
  [the UI copy guide](docs/UI_COPY_GUIDE.md).
- The showcase is light-theme only by design.

The browser stores the access token in `localStorage`. That is acceptable for this local prototype
but production deployments should use secure, HTTP-only cookies and refresh-token rotation.

## Engineering conventions

- Business rules (compliance norms, SLA durations, alert templates) live in the database as
  data, never hard-coded in services.
- Every write and state change must be recorded by the audit log service in the same transaction.
- Workflow status changes must go through the workflow state machine only.
- All list endpoints are paginated and role-protected.
- See `AGENTS.md` for the full project rules.

## Documentation

- [Entity-relationship diagram](docs/er-diagram.md)
- [UI copy guide](docs/UI_COPY_GUIDE.md)

## Known gaps

- Notification delivery uses a plain SMTP relay (Mailpit in development) without a durable retry
  queue, and SMS is a logging mock behind the provider interface. Production delivery would need
  outbox/retry, bounce handling and a real gateway.
- Required-document rules and SLA durations are data, but there is no admin configuration screen
  for them yet. Seeded values can be edited directly in the `required_documents` and `sla_configs`
  tables. Compliance rules, weights, status bands and alert rules do have admin screens at
  `/compliance` and `/alert-rules`.
- Programmes are captured but do not block submission in this increment. Submitted application
  section data, programmes and the document browser (with reject, re-upload and verify) are
  visible on the detail page.
- `MAX_REUPLOADS_PER_DOCUMENT` is an environment setting, not an admin screen: changing the
  replacement cap needs a restart. The handbook sets no cap, so the seeded value is an assumption
  (OQ-53, OQ-54).
- The upload-time PDF readability check uses `pdfplumber` text extraction and falls back to a
  printable-text heuristic when a PDF cannot be parsed. A valid but unusual PDF is therefore
  accepted with a warning rather than blocked; a reviewer can still reject it with a reason code
  (OQ-57).
- The demo SLA dates in the seed are illustrative scaffolding. Real SLA durations and compliance
  thresholds must come from editable configuration and be reviewed against the current AICTE
  Approval Process Handbook.
- Authentication currently issues access tokens only; refresh tokens, password reset, account
  lockout and MFA are out of scope for this increment.
- Audit regional scoping covers institution, application and user entities directly; other
  polymorphic entity types rely on the actor's region or should add explicit region metadata when
  those modules are built.
- The public login screen retains the original navy/saffron brand treatment. Authenticated shell
  and product surfaces use the design-system tokens.
- `/dev/ui` is intentionally public for review. Protect or remove it before a production
  deployment.
# SIH_2026
