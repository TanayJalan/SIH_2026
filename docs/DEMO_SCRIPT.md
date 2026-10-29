# Demo Script — 6-Minute Click Path

**Purpose**: End-to-end walkthrough of the AICTE approval workflow from institution
registration through approval, appeal, and time-simulation. Runs from a fresh
database with `make seed` (followed by `make reset-demo` to reset the demo clock).

---

## Prerequisites

```bash
make dev          # start the stack (DEBUG=true is required)
make seed-aph     # generate APH config from APH_SPEC.md
# Demo data seeding is handled by the backend on first run;
# see Notes below.
open http://localhost:5173
```

- Backend must run with `DEBUG=true` (set via `DEBUG=true docker compose up -d`).
- All sample institutions and data are **fictional**; thresholds and dates are
  illustrative (must be verified against the current AICTE Approval Process Handbook).
- The demo uses 15 institutions across 5 states/regions and 10 role accounts
  (`ChangeMe123!` password).

---

## 1. Institution Wizard — Fee & Deficiency Report

**User**: `institution@example.edu` (INSTITUTION_ADMIN, west state)

1. Log in → **My applications** → **New application** → Select **New institution** (Chapter I).
2. Fill the wizard:
   - Institution name, address, contact details.
   - **Fee payment**: `INSTITUTION_ADMIN` → **Pay Application Fee** → submit payment
     (generates a fee transaction record; amount configurable in `fee_schedules.json`).
   - **Deficiency Report**: The system auto-raises two initial deficiencies:
     - *Expired fire safety certificate* (APH 6.8) — marked `HIGH` severity.
     - *Missing DSC* (APH 2.24) — marked `CRITICAL` severity.
   - Both deficiencies appear in the **Deficiency Report** sidebar; the institution
     must respond before proceeding.

**Expected UI**: Institution dashboard shows two pending deficiencies, fee status
`paid`, and **Allowed Actions** button **Raise Response to Deficiencies**.

---

## 2. Committee Auto-Selection > Scrutiny Deficiency

**User**: `scrutiny@example.edu` (SCRUTINY_COMMITTEE_MEMBER, assigned officer)

1. Open the case file for the institution's application.
2. The **EscalationBadge** shows `Escalated` if the deficiency count > 0.
3. Click **Raise Response to Deficiencies** → the system auto-selects the
   **Scrutiny Committee** as the reviewing body (APH 1.9a).
4. For each deficiency:
   - **Expired fire certificate**: upload a replacement certificate or mark `resolved`.
   - **Missing DSC**: upload the DSC certificate file; verify status changes from
     `EXPIRED`/`PENDING` to `VERIFIED`.
5. Click **Submit Responses** → the system records a `WorkflowEvent` with action
   `deficiency_response` and APH clause `APH 2.24`; the **EscalationBadge**
   clears if all deficiencies are resolved.

**Expected UI**: Deficiency Report now shows `0` open deficiencies; the case
progresses to the **Scrutiny** stage.

---

## 3. Institution Responds > EVC > EC Decision & Council Ratification

**User**: `regulation@example.edu` (REGULATION_BUREAU_OFFICER)

1. In the case file, the next **Allowed Action** is **Place Regulation Bureau observations**.
2. Click it → enter observations text (e.g. `"Infrastructure and faculty verified;
   recommend placing before the Executive Committee for the LoD decision."`) → submit.
3. The case status becomes `REGULATION_BUREAU_OBSERVATIONS`; a new **Allowed Action**
   appears: **List before the Executive Committee**.
4. Click **List before the Executive Committee** → the case is placed on the EC agenda.
   The **Allowed Actions** for `ec@example.edu` (EXECUTIVE_COMMITTEE_MEMBER) now
   include **Decide to approve (LoA)** and **Decide to reject (LoR)**.

**As `ec@example.edu`**: Click **Decide to approve (LoA)** → a dialog appears with:
   - **Decision outcome**: select **Letter of Approval (LoA)**.
   - **Decision notes** (optional): e.g. `"Fresh demo LoA decision via EC_DECISION; produced INSTITUTION_ADMIN LoA path."`
   - **Quorum met**: confirm (APH 1.10a).
   - Submit → the system records a `Decision` row (outcome `LOA`, `quorum_met=true`)
     and a `DecisionLetter` of type `LOA`.

5. The case status advances to `EC_DECISION`; the **Decision & Letters** tab now
   lists the LoA record with **PDF download** and **Acknowledge** button.
6. Click **Acknowledge** → records acknowledgement (APH 1.11a) and triggers a
   success toast.

**As `super_admin@example.edu`** (optional, for Council ratification):
7. Open the **Council Ratification** flow → confirm the LoA → the case status
   advances to `COUNCIL_RATIFICATION`; the **Decision & Letters** tab lists the
   ratified LoA; a toast confirms **Council ratification complete**.

---

## 4. Letter PDF with Speaking Order

- In the **Decision & Letters** tab, click **PDF download** for the LoA record.
- The generated PDF includes:
  - Institution name, application reference, LoA number.
  - Decision outcome, date, signing authority (EXECUTIVE_COMMITTEE_MEMBER).
  - A Speaking Order section (present when the decision is a rejection/LoR);
    for LoA the section notes "No speaking order required — approval issued."
- The PDF is styled per APH_SPEC §1.10b and is downloadable as `loa_{app_id}.pdf`.

---

## 5. Appeal and 7-Day Clock

After the LoA is issued, the ** seven-day appeal window** (APH 1.11a) opens.

1. In the case file, the **Allowed Actions** now include **File appeal** (visible to
   the institution admin).
2. Click **File appeal** → a dialog appears with the appeal deadline:
   **7 days from now** (the demo clock is initially set to real time, 29 Oct 2026).
3. The **CaseDecisionLetters** section shows the appeal deadline label:
   `"7 days left to appeal"` (countdown computed from the simulated clock).
4. The **SlaRing** in the header shows the remaining SLA window days.
5. **Time simulation**: Click the **Demo time controls** button → **Advance 7 days**.
   - The simulated clock jumps forward 7 days (e.g., to 5 Nov 2026).
   - The appeal countdown updates live: `"0 days left to appeal"` / `"appeal expired"`.
   - A **CRITICAL** toast appears: `"SLA breached: the 7-day appeal window closed."`
   - The **EscalationBadge** flips to `Escalated`; the **Bell count** increments
     (new alert pushed via SSE `alert` frame).
   - The **Dashboard** countdown cards refresh (invalidated via `[\"alerts\"]` and
     `[\"time-simulation\"]`).

**To verify the 2-second acceptance criterion**: after clicking **+7 days**, observe
that the countdown flips, the CRITICAL toast appears, and the bell count changes —
all within 2 seconds of the button click (confirmed by live browser run with 100 ms
sampling).

---

## 6. Time Simulation (`+8 days`) with Live Alerts & Escalation

The demo includes a **Dev time control** that advanced the simulated clock
incrementally. Beyond the +7 day appeal crossing, additional advances trigger
further SLA-based alerts:

| Advance | Trigger | Visual Effect |
|---------|---------|--------------|
| `+1 day` | Deadline approaching (T-1) | Info toast: `"Deadline approaching: … (T-1)"`; countdown drops 1 day; bell +1. |
| `+3 days` | SLA warning | Medium toast; countdown drops 3 days. |
| `+7 days` | SLA breached | **CRITICAL** toast persists (duration ~24 days); escalation badge `Escalated`; bell +3. |
| `+15 days` | Security Deposit penalty ladder starts | Medium/high alerts for penalty steps (APH 2.25f). |
| `+365 days` | LoA validity expires (APH 1.10b) | Critical toast: `"Letter of Approval expired; fresh EoA required."` |

**Reset**: At any point, click **Reset to real time** (Dev time control) → the
simulated clock snaps back to the current real date (e.g., 29 Oct 2026); all
countdowns revert; bell and toast state clears; the demo is ready for a fresh
walkthrough.

---

## Notes on `make seed` and Demo Data

- `make seed-aph` generates `backend/seeds/aph/*.json` from `docs/reference/APH_SPEC.md`.
- `make seed` applies alembic migrations and seeds 15 institutions, 10 demo user
  accounts (one per APH role, password `ChangeMe123!`), and 5 pre-staged application
  cases (see below). **Note**: the full seed command has known enum-alignment issues
  with `institution_class` and `aicte_region`; these can be resolved by editing the
  generated JSON or by running limited manual seeding.
- Pre-staged cases (visible immediately after seed):
  1. **EoA self-disclosure** ready to submit, with two deficiencies (expired fire cert +
    missing DSC) — Case 1.
  2. **New-institution** at Scrutiny with a deficiency (missing DSC) — Case 2.
  3. **LoR issued**, 7-day appeal window running — Case 3.
  4. **LoA recommended**, Security Deposit pending (day 5 of 15) — Case 4.
  5. **Clean institution**, Nil Deficiency — Case 5.
- To reset the demo clock without re-seeding: `POST /dev/simulate-time {"reset": true}`
  (available when `DEBUG=true`). This resets the simulated clock to real time and
  clears countdowns/bell state, but previously created alerts may dedupe on re-crossing.
- For a completely fresh state, run `make down` (stops containers, preserves DB volume)
  then `make dev && make seed-aph` and manually seed a few cases via the API or TUI.

---

## Acceptance — From a Fresh Database

1. `make dev` (starts stack with `DEBUG=true`).
2. `make seed-aph` (generates config).
3. `make seed` (applies migrations + seeds demo data — may need manual enum fixes).
4. Open `http://localhost:5173`, log in as `institution@example.edu` (west admin).
5. Follow the 6-minute click path above — all live SSE updates, countdown flips,
   toast persistency, and escalation badges should occur within the 2-second
   sampling window verified by browser runs.
6. As a final verification, click **Demo time controls** → **Advance 7 days** →
   confirm the CRITICAL toast, bell count change, and countdown expiry all appear
   within 2 seconds.

---
*Generated for Smart India Hackathon 202.0 prototype. All AICTE data is fictional;*
*compliance thresholds are illustrative and must be verified against the current*
*AICTE Approval Process Handbook (APH 2024-27).*
