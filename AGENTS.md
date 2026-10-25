# Project
"Integrated AICTE Approval Workflow Automation, Compliance Monitoring and Alert Management System". A Smart India Hackathon prototype. It digitizes the AICTE approval cycle for technical institutions: application, document verification, scrutiny, inspection, decision. It continuously monitors compliance against AICTE norms and raises alerts with escalation.

# Scope (MVP, do not exceed)
ONE deep flow: "New/Extension of Approval for a technical institution (Engineering/Management)". Everything else is out of scope.

# Stack
- Backend: Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, PostgreSQL (docker-compose), APScheduler for scheduled jobs (no Redis/Celery)
- Frontend: React + Vite + TypeScript + Tailwind + Recharts + React Router + TanStack Query
- Auth: JWT (access token) with role-based access control
- ML: scikit-learn (RandomForest/GradientBoosting), joblib
- Docs: pdfplumber for PDF text extraction (optional pytesseract if installed)
- Notifications: in-app (DB), email via SMTP (Mailpit in docker-compose for demo), SMS is a mock provider behind an interface

# Roles
INSTITUTION_ADMIN, SCRUTINY_OFFICER, INSPECTION_COMMITTEE, REGIONAL_HEAD, SUPER_ADMIN

# Engineering rules
1. Monorepo: /backend, /frontend, /docs, docker-compose.yml, Makefile
2. Business rules (compliance norms, SLA durations, alert templates) are DATA (DB rows/JSON config), never hard-coded in logic.
3. Every state change and every write action goes through an audit log service (who, what, when, before/after JSON, IP).
4. Workflow transitions are enforced by a single state machine; no endpoint may set status directly.
5. All endpoints have Pydantic schemas, proper HTTP status codes, role checks, pagination where lists are returned.
6. Write pytest tests for the workflow engine, compliance engine and alert engine (they are the core).
7. Keep code typed, small functions, docstrings on services. No dead code, no TODO placeholders in shipped paths.
8. Provide a `make dev`, `make seed`, `make test` command.
9. Never invent real AICTE data. All sample institutions are clearly fictional. Compliance threshold values are ILLUSTRATIVE and must be editable from an admin screen. Note in README that they must be verified against the current AICTE Approval Process Handbook.
10. After finishing each task, summarize what was built, how to run it, and any known gaps.

Confirm by printing the file path. Do not start building yet.

---

# Domain source of truth
docs/reference/APH_SPEC.md is the authoritative domain specification (from docs/reference/APH_2024-27.pdf; text copy APH_2024-27.txt).
1. Every rule, fee, deadline, document requirement, committee or workflow transition must carry an apH_clause value (for example "APH 1.11a") taken from APH_SPEC.md.
2. If something is not in APH_SPEC.md, grep the .txt copy. If still not found, create it with needs_verification=true and list it in docs/OPEN_QUESTIONS.md. Never invent norms, fees or dates.
3. Items marked with the warning sign in APH_SPEC.md section 12 are ambiguous: implement them as configurable parameters and list them in docs/OPEN_QUESTIONS.md.
4. Cut-off dates, committee dates and processing-time limits are NOT in the handbook. They live in PublicNotice, AcademicCalendarEvent and SLAConfig tables (admin-editable, seeded with clearly labelled demo values).

# Vocabulary (use exactly in code and UI)
Regulation Bureau, Regional Officer, Scrutiny Committee, Re-Scrutiny Committee, Expert Visit Committee (EVC), Standing Hearing Committee (SHC), Standing Appellate Committee (SAC), Standing Complaint Scrutiny Committee (SCSC), PGRC, Executive Committee (EC), Council, LoA, LoD, LoR, Speaking Order, EoA, Extended EoA, Approved Intake, TER charges, Security Deposit, Self-Disclosure, Deficiency Report, Nil Deficiency.

# Engineering additions
- Money is stored as integer paise (never float). Fee tables live in the DB with clause references.
- Deadlines are computed in one DeadlineService.
- Every eligibility or compliance decision returns an explanation: criteria, values, pass/fail, clause.
- Calculators are pure functions with unit tests built from worked examples in APH_SPEC.md.
- A test must fail the build if any ComplianceRule, WorkflowTransition, FeeSchedule or AlertRule row lacks apH_clause (unless needs_verification=true).
