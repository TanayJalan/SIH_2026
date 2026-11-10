# API guide

The backend is a FastAPI service. The generated schema is the source of truth for request and
response fields:

- Interactive docs: `http://localhost:8000/docs` (Swagger UI) and `/redoc`
- Machine-readable schema: `http://localhost:8000/openapi.json`
- Checked-in copy: `docs/openapi.json` (regenerate with `make openapi`)

This guide covers conventions, the endpoint map and the role expectations. Field-level schemas live
in `backend/app/schemas/` and in the OpenAPI document.

## 1. Conventions

| Topic | Convention |
| --- | --- |
| Base URL | `http://localhost:8000` in development; the public API origin in production |
| Auth | `Authorization: Bearer <access_token>` except for health, public stats, login and the dev router |
| Content type | `application/json`, except document upload (`multipart/form-data`) and PDF/download responses |
| Dates | ISO 8601. Timestamps are UTC (`2026-11-10T05:30:00Z`); dates are `YYYY-MM-DD` |
| Money | Integer **paise** in every request and response. Never a float |
| Clause citations | Configuration and explanation objects carry `apH_clause`; unresolved rows set `needs_verification=true` |
| Pagination | `page` (≥1) and `page_size` (1–100, default 20). Responses return `items`, `total`, `page`, `page_size`, `pages` |
| Errors | `{"detail": "..."}` for simple errors; validation errors use FastAPI's `detail` array. Status codes: 400, 401, 403, 404, 409, 413, 415, 422, 429, 503 |
| Request ID | Every response carries `X-Request-ID`; send one to correlate logs |
| Rate limiting | Repeated failed logins return `429` with `Retry-After` |
| Demo clock | `/dev/simulate-time` exists only when `DEBUG=true` |

### Authentication example

```bash
curl -s http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"institution@example.edu","password":"ChangeMe123!"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": "...",
    "name": "Demo Institution Administrator",
    "email": "institution@example.edu",
    "role": "INSTITUTION_ADMIN",
    "institution_id": "...",
    "institution": {"id": "...", "name": "Demo Institute of Technology", "aicte_id": "..."},
    "region": "Pune",
    "is_active": true
  }
}
```

```bash
TOKEN=$(curl -s http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"institution@example.edu","password":"ChangeMe123!"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
```

### Error example

```json
{"detail": "Only the assigned scrutiny officer can perform this action"}
```

### Pagination example

```bash
curl -s 'http://localhost:8000/applications?page=1&page_size=20&sort=due' \
  -H "Authorization: Bearer $TOKEN"
```

```json
{"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}
```

## 2. Endpoint map

Role notes are a summary; the authoritative checks are in the route modules and
`app/services/authorization.py`. See `docs/RBAC.md` and `docs/SECURITY.md` for the matrix.

### System and public

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | Public | Liveness probe |
| GET | `/health/ready` | Public | Database readiness probe |
| GET | `/public/stats` | Public | Anonymised demo statistics for the landing page |

### Authentication

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/login` | Public | Validate credentials, issue a JWT |
| GET | `/auth/me` | Any authenticated | Current profile, role and institution |

### Applications (read)

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/applications` | Scoped by role | Paginated list (`overdue`, `assigned_to_me`, `sort=recent` or `sort=due`, `institution_id`) |
| GET | `/applications/type-routes` | Any authenticated | Configured APH application types and routing flags |
| GET | `/applications/{application_id}` | Scoped by role | Application detail |
| GET | `/applications/{application_id}/compliance` | Scoped by role | Latest per-rule compliance results and score |

### Institution workspace

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/applications` | Institution admin, Super admin | Create a draft |
| PATCH | `/applications/{id}` | Owner | Update section data |
| DELETE | `/applications/{id}` | Owner | Delete a draft |
| GET | `/applications/{id}/checklist` | Owner / reviewer | Completeness checklist |
| GET | `/applications/{id}/documents/checklist` | Owner / reviewer | Required-document checklist with upload state |
| GET | `/applications/{id}/document-shells` | Owner / reviewer | Placeholder shells for the wizard |
| GET | `/applications/{id}/document-shells/{doc_code}` | Owner / reviewer | One document shell |
| POST | `/applications/{id}/compliance/preview` | Owner | Evaluate draft data before submission |
| GET | `/applications/{id}/programs` | Owner / reviewer | Programmes on the application |
| POST | `/applications/{id}/programs` | Owner | Add a programme |
| PATCH | `/applications/{id}/programs/{program_id}` | Owner | Edit a programme |
| DELETE | `/applications/{id}/programs/{program_id}` | Owner | Remove a programme |
| POST | `/applications/{id}/submit` | Owner | Run completeness checks and submit |
| POST | `/applications/{id}/reopen` | Owner | Reopen after a deficiency, recording a fresh TER |

### Documents

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/applications/{id}/documents` | Scoped by role | Current document versions |
| GET | `/applications/{id}/documents/{document_id}/versions` | Scoped by role | Version history |
| POST | `/applications/{id}/documents` | Owner | Upload a new document (multipart) |
| POST | `/applications/{id}/documents/{document_id}/reupload` | Owner | Replace a rejected/flagged document |
| POST | `/applications/{id}/documents/{document_id}/reject` | Scrutiny, Bureau, Super admin | Reject with a reason code |
| POST | `/applications/{id}/documents/{document_id}/verify` | Scrutiny, Bureau, Super admin | Verify or flag a document |
| GET | `/applications/{id}/documents/{document_id}/download` | Scoped by role | Download the stored file |

Uploads accept PDF, JPEG and PNG up to 10 MB. The type is detected from magic bytes, not the
filename, and the stored name is a random UUID.

### Fees and Security Deposit

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/applications/{id}/fee` | Owner / Bureau / Super admin | Fee quote and payment state |
| POST | `/applications/{id}/fee/pay` | Owner | Record a fee payment (no gateway) |
| POST | `/applications/{id}/fee/refund` | Owner / Bureau / Super admin | Record a refund or deduction |
| GET | `/applications/{id}/fee/transactions` | Scoped by role | Fee transaction history |
| GET | `/applications/{id}/security-deposit-quote` | Owner / reviewer | Table 1.4 quote |
| GET | `/applications/{id}/security-deposits` | Scoped by role | Deposits for the application |
| GET | `/security-deposit-clearances` | Clearance roles | Pending PGRC/Vigilance clearances |
| POST | `/applications/{id}/security-deposits/{deposit_id}/release-request` | Owner, Super admin | Request release |
| POST | `/applications/{id}/security-deposits/{deposit_id}/clearance` | Clearance roles | Record a clearance |
| POST | `/applications/{id}/security-deposits/{deposit_id}/release` | EC / Super admin | Record release |
| POST | `/applications/{id}/security-deposits/{deposit_id}/withdraw` | Owner, Super admin | Withdraw the request |

### Workflow

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/applications/{id}/actions/{action}` | Transition-specific role | Perform one workflow action |
| GET | `/applications/{id}/timeline` | Scoped by role | Workflow event timeline |
| GET | `/applications/{id}/allowed-actions` | Scoped by role | Actions legal for this user and state |
| GET | `/applications/{id}/deficiencies` | Scoped by role | Deficiency Report items |
| GET | `/applications/{id}/inspections` | Scoped by role | EVC inspections |
| GET | `/applications/{id}/committee-members` | Scoped by role | Selected committee members |
| GET | `/applications/{id}/letters` | Scoped by role | LoA/LoD/LoR/Speaking Orders |
| POST | `/applications/{id}/appeal` | Owner | File an appeal inside the 7-day window |
| GET | `/applications/{id}/deadlines` | Scoped by role | Statutory timers and appeal deadline |
| GET | `/applications/{id}/appeal` | Scoped by role | Appeal details |
| GET | `/applications/{id}/decisions` | Scoped by role | Decision records |
| GET | `/applications/{id}/deficiency-report` | Owner / reviewer | Deficiency Report data |
| GET | `/applications/{id}/deficiency-report.pdf` | Owner / reviewer | Deficiency Report PDF |
| GET | `/workflow/definition` | Any authenticated | States, transitions and roles |
| GET | `/workflow/diagram` | Any authenticated | Rendered workflow diagram data |

`action` is a `WorkflowAction` enum value (for example `SUBMIT`, `START_SCRUTINY`,
`COMMUNICATE_DEFICIENCY`, `EVC_REPORT`, `EC_DECIDE`). The server rejects an action that the role,
state or guards do not allow; it also rejects direct status changes because no such endpoint exists.

```bash
curl -s -X POST \
  http://localhost:8000/applications/$APPLICATION_ID/actions/START_SCRUTINY \
  -H "Authorization: Bearer $OFFICER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### Letters

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/letters/{letter_id}` | Scoped by role | Letter metadata |
| GET | `/letters/{letter_id}/download` | Scoped by role | Download the generated document |
| POST | `/letters/{letter_id}/acknowledge` | Owner | Acknowledge receipt |

### Compliance

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/compliance/rules` | Super admin, Regional Officer | Rule library |
| POST | `/compliance/rules` | Super admin, Regional Officer | Add a rule |
| PATCH | `/compliance/rules/{rule_id}` | Super admin, Regional Officer | Edit a rule |
| GET | `/compliance/rules/{rule_id}/history` | Super admin, Regional Officer | Rule change history |
| POST | `/compliance/rules/impact` | Super admin, Regional Officer | Preview threshold impact |
| GET | `/compliance/metrics` | Super admin, Regional Officer | Available metrics |
| GET | `/compliance/config` | Super admin, Regional Officer | Weights, RAG bounds, norms |
| PUT | `/compliance/config` | Super admin, Regional Officer | Replace configuration |
| GET | `/compliance/monitor` | Super admin, Regional Officer | Monitoring status |
| POST | `/compliance/monitor/run` | Super admin, Regional Officer | Run an on-demand evaluation |
| GET | `/compliance/institutions/{institution_id}/trend` | Super admin, Regional Officer | Snapshot trend |

### Alerts

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/alerts` | Authenticated | Current user's paginated inbox |
| GET | `/alerts/summary` | Authenticated | Unread/acknowledged counts by severity |
| GET | `/alerts/stream` | Authenticated | Server-Sent Events: `alert`, `time`, `connected` |
| POST | `/alerts/{alert_id}/ack` | Recipient | Acknowledge and stop escalation |
| GET | `/alert-rules` | Super admin | Alert rule list |
| GET | `/alert-rules/{rule_id}` | Super admin | One rule |
| POST | `/alert-rules` | Super admin | Add a rule |
| PATCH | `/alert-rules/{rule_id}` | Super admin | Edit a rule |
| DELETE | `/alert-rules/{rule_id}` | Super admin | Disable/delete a rule |

The SSE route accepts the token as a query parameter because `EventSource` cannot set an
`Authorization` header:

```text
GET /alerts/stream?token=<access_token>
```

Frames look like:

```text
event: alert
data: {"id":"...","type":"DOCUMENT_EXPIRING","severity":"MEDIUM","title":"Document expiring: ...","message":"...","application_id":"...","escalation_level":0,"channel":"IN_APP","apH_clause":"APH Annexure-2.1"}

event: time
data: {"simulated_now":"2026-11-12T10:00:00+00:00","offset_days":2}
```

### Audit

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/audit-logs` | Super admin, Regional Officer, Regulation Bureau | Filter by entity, actor and UTC date range |

### Reports

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/reports/regulation-bureau` | Bureau, Scrutiny | Work queue, deficiencies, inspections, SLA breaches |
| GET | `/reports/regional` | Regional Officer, Super admin | Funnel, decisions, appeals, fees, complaints, compliance |
| GET | `/reports/institution` | Institution admin | Own application progress and compliance |
| GET | `/reports/application/{application_id}.pdf` | Scoped by role | Full application report PDF |

Report filters: `academic_year`, `region`, `state`, `application_type`, `track`.

### Search

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/search?q=` | Authenticated | Role-scoped search across applications, institutions and permitted pages |

### Committees

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/expert-pool` | Panel roles | Expert pool list |
| GET | `/expert-pool/{expert_id}` | Panel roles | Expert detail |
| POST | `/committees/select` | Selection roles | Select a committee for a case |
| GET | `/committees/application/{application_id}` | Scoped by role | Committees for a case |
| GET | `/committees/{committee_id}` | Scoped by role | Committee detail |
| GET | `/committees/quorum/{committee_type}` | Panel roles | Required quorum |

### Complaints and penal actions

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/complaints/catalogue` | Authenticated | Complaint categories and statuses |
| GET | `/complaints` | Scoped by role | Complaint list |
| POST | `/complaints` | Institution admin, Super admin | File a complaint |
| GET | `/complaints/{complaint_id}` | Scoped by role | Complaint detail |
| POST | `/complaints/{complaint_id}/verify` | Verification roles | Verify admissibility |
| POST | `/complaints/{complaint_id}/scsc-decision` | SCSC | Record the SCSC decision |
| POST | `/complaints/{complaint_id}/show-cause-reply` | Institution admin, Super admin | Submit the reply |
| POST | `/complaints/{complaint_id}/shc-hearing` | SHC | Record the hearing |
| POST | `/complaints/{complaint_id}/ec-decision` | EC | Record the EC decision |
| GET | `/penal-actions/catalogue` | Authenticated | APH 7.3 action catalogue |
| GET | `/complaints/{complaint_id}/penal-actions` | Scoped by role | Penal actions for a complaint |
| POST | `/complaints/{complaint_id}/penal-actions` | EC / Super admin | Create a penal action |
| GET | `/penal-actions/{penal_action_id}` | Scoped by role | Penal action detail |
| POST | `/penal-actions/{penal_action_id}/hearing` | SHC | Record the penal hearing |
| POST | `/penal-actions/{penal_action_id}/issue` | EC / Super admin | Issue the action |
| POST | `/penal-actions/{penal_action_id}/restoration-request` | Restoration roles | Request restoration |
| GET | `/applications/{application_id}/excess-admission-fine` | Scoped by role | APH 7.3g fine calculation |

### Development only

Mounted only when `DEBUG=true`:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/dev/simulate-time` | Read the simulated clock offset |
| POST | `/dev/simulate-time` | Advance or reset the demo clock |

## 3. Status codes that matter

| Code | When |
| --- | --- |
| 400 | Malformed request that is not a Pydantic validation error |
| 401 | Missing, expired or invalid token; bad credentials |
| 403 | Authenticated but role or record scope denies the action |
| 404 | Record not found, or not visible to this user |
| 409 | State conflict, e.g. editing a submitted application or re-uploading outside a compliance window |
| 413 | Upload larger than 10 MB |
| 415 | Upload is not PDF, JPEG or PNG (detected from content) |
| 422 | Schema validation, missing required document, illegal workflow payload |
| 429 | Login throttled; `Retry-After` says how long |
| 503 | Application type is not implemented in this MVP |

## 4. Regenerating the OpenAPI document

```bash
make openapi          # writes docs/openapi.json from the running backend
```

The script is `backend/scripts/export_openapi.py`. Commit the regenerated file when routes or
schemas change so reviewers can diff the contract without running the stack.
