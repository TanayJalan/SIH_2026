# Roadmap

The MVP proves one deep flow: New/Extension of Approval for an Engineering/Management institution,
with configurable compliance monitoring and alert escalation. This roadmap separates what is
already demo-ready from what must be built before a pilot and what would be needed for a real
rollout. It is not a commitment; it is an ordering of risk.

## 1. Where the prototype stands

Shipped and exercised by tests:

- Data-driven workflow state machine with role, scope and guard checks, audit rows and workflow
  events.
- Institution workspace: drafts, programmes, required-document checklist, versioned uploads,
  submission, reviewer rejection and re-upload.
- Compliance engine with APH calculators, clause-cited rules, weighted scores, Nil Deficiency gate,
  snapshots, nightly monitoring and admin editing.
- Alert engine with eight trigger families, dedupe keys, in-app/email/mock-SMS delivery, SSE live
  updates, acknowledgement and a three-step escalation chain.
- Reports for the Regulation Bureau, Regional Officer and Institution Admin, plus a PDF application
  report.
- JWT auth, RBAC, region/assignment scoping, append-only audit trail, login throttling, security
  headers and production configuration validation.
- Playwright smoke tests and an 80% coverage gate on the core modules.
- Development and production Compose profiles.

## 2. P0 — before any real user or data

These are blocking for a pilot, not for a hackathon demo.

| Item | Why | Done when |
| --- | --- | --- |
| Verify every `needs_verification` row | A wrong threshold or date is a wrong decision | `docs/OPEN_QUESTIONS.md` has no OPEN row that affects a live flow; config test still green |
| Verify fee tables, cut-off dates and calendar events against the current APH | Demo values are explicitly fictional | Admin has replaced demo rows; `is_demo=false` on used rows |
| Region-scope the regional dashboard | A Regional Officer currently sees national aggregates (OQ-75) | `/reports/regional` returns only the officer's region, with a separate national comparison view if needed |
| Move login throttling to a shared store | Per-process limits multiply with workers | Redis-backed limiter, or a gateway limiter, covered by a two-worker test |
| Replace demo accounts and passwords | Seeded credentials are public | Demo users deleted or rotated; seed refuses to run in production |
| Back up and restore drill | Audit and decisions must survive loss | Restore of `audit_logs` and the document volume verified |
| TLS, proxy headers and HSTS | Tokens and documents travel over the network | Production profile behind a TLS proxy; HSTS observed |

## 3. P1 — pilot hardening (next)

### Security

- Refresh tokens with rotation and reuse detection; short access tokens.
- HttpOnly, `SameSite=Strict` cookie session with CSRF protection (or a backend-for-frontend), so
  the JWT is no longer in `localStorage`.
- Short-lived ticket or cookie auth for the SSE stream instead of a token in the query string.
- MFA (TOTP/WebAuthn) for `SUPER_ADMIN`, `REGIONAL_OFFICER`, `REGULATION_BUREAU_OFFICER` and
  committee roles.
- Antivirus/content-disarm for uploads; quarantine bucket and scan status.
- Dependency scanning (`pip-audit`, `npm audit`, Dependabot) and a CI gate.
- Alerting on repeated `auth.rate_limited`, impossible-travel patterns and bulk downloads.
- Database role separation: the app role cannot `UPDATE`/`DELETE` `audit_logs`; export audit rows
  to WORM storage or a SIEM.

### Scale and reliability

- Redis for login limiting, SSE fan-out and the scheduler lock.
- A single scheduler leader (or an external scheduler) when `WEB_CONCURRENCY > 1` or replicas > 1.
- Durable outbox for email/SMS with retries and dead-letter handling.
- Pagination and filtering pushed into SQL for every list; load-test the seeded dataset at 10×
  volume.
- `CREATE INDEX CONCURRENTLY` workflow for large tables.
- Health/readiness metrics, structured error budget and dashboards.

### Functional

- Region-scoped reports and per-committee case membership.
- Admin UI for `application_type_routes`, `fee_schedules`, `security_deposit_schedules`,
  `public_notices`, `academic_calendar_events`, `committees` and `security_deposits`.
- Complete the scenario seed data so a "clean" case scores as clean (OQ-76).
- Appeal and complaint flows end to end, including restoration filing (OQ-67).
- Security Deposit release UI for PGRC/Vigilance clearances.
- Letter templates reviewed by legal; digital signature integration.

### Operations

- CI pipeline: lint, typecheck, backend tests, coverage gate, frontend build, Playwright against a
  disposable stack.
- Staging environment with anonymised data.
- Backup schedule, retention policy and restore runbook.
- Log retention and PII redaction review.
- On-call runbook for failed migrations, stuck scheduler and mail backlog.

## 4. P2 — production readiness (later)

- Horizontal API scaling with shared session/limiter/broker state.
- Read replicas for reports if aggregate queries become the bottleneck.
- Object storage (S3-compatible) for documents with lifecycle rules and server-side encryption.
- Full observability: OpenTelemetry traces, metrics, alerting and SLOs.
- Accessibility audit (WCAG 2.2 AA) and Hindi/regional language UI.
- Mobile-friendly officer workflow for inspections.
- ML risk scoring and anomaly detection, trained only on approved, anonymised data.
- Data retention and erasure policy aligned with applicable government rules.
- Independent security review and penetration test.
- Load and failover testing; disaster-recovery exercise.

## 5. Explicit non-goals for the MVP

- Real AICTE data, real fee amounts or real cut-off dates.
- Every application type in Table 2.2. Types not implemented return HTTP 503 rather than a guessed
  path.
- A distributed workflow engine, message bus or microservices split.
- A native mobile app.
- ML risk scoring (the interface is reserved, the model is not shipped).
- SMS delivery beyond the mock provider.
- Payment gateway integration; fee payment is recorded, not processed.

## 6. Release criteria

A release is demo-ready when:

1. `make test`, `make coverage`, `make e2e` and the frontend typecheck/build pass on a clean clone.
2. `docker compose -f docker-compose.prod.yml config` validates with a filled
   `.env.production`.
3. Every configuration row has an `apH_clause` or `needs_verification=true`.
4. The security checklist in `docs/SECURITY.md` is complete for the target environment.
5. No P0 item in this roadmap remains open for the data being used.

A release is pilot-ready when the P0 table is complete, the P1 security items that apply to the
deployment are complete, and a restore drill has succeeded.
