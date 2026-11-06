# Demo Script — Seven-Minute Walkthrough

One story, five screens: an institution's case file, the committee draw, the
Expert Visit video, the Deficiency Report issued from failed rules, the
institution's response, and the time simulation that expires the statutory
clocks and escalates.

Everything in the database is **fictional**. Compliance thresholds, fees,
cut-off dates and SLAs are editable configuration rows that still need checking
against the current AICTE Approval Process Handbook. Say this out loud in the
first ten seconds; a judge will ask.

---

## Before you start (once, ~40 seconds)

```bash
make dev            # stack up; DEBUG=true is the Compose default and powers Demo time
make reset-demo     # drop the schema, migrate, seed: ~12 s, leaves a clean demo
docker compose restart backend   # clears the in-process Demo time offset
open http://localhost:5173
```

`make seed` is enough on a fresh clone; `make reset-demo` is the reliable reset
between runs. The simulated clock lives in the **backend process**, not the
database, so restart the backend (or click **Demo time → Reset to real time**)
before a run that follows an earlier time advance.

Accounts used below, all with password `ChangeMe123!` (the login screen lists
them under **Demo accounts** and fills the form when you pick one):

| Window | Account | Role |
| ------ | ------- | ---- |
| A | `institution@example.edu` | Institution admin, MAH-0001 |
| B | `regulation@example.edu` | Regulation Bureau officer |
| C | `scrutiny@example.edu` | Scrutiny Committee member |
| D | `inspection@example.edu` | Expert Visit Committee member |
| E | `admin@example.edu` | Super admin (national oversight) |

Open A–E in separate browser profiles or windows and sign in **before** the
clock starts. Seven sign-ins inside the run will eat the demo.

The two portal numbers on screen all evening:

- `AICTE/2026-27/0000109` — the live case (MAH-0001, at Scrutiny, assigned to
  `scrutiny@example.edu`).
- `AICTE/2026-27/0000102` — the increase-in-intake case with a scheduled EVC
  visit (MAH-0002).

---

## 0:00–0:30 — Frame

> "AICTE's approval cycle is application, scrutiny, deficiency loop, expert
> visit, decision, appeal. We digitise the whole loop: every rule cites its APH
> clause, every transition runs through one state machine, and every write is
> audited. Norms, fees, deadlines and alert templates are database rows an
> administrator can edit — nothing is hard-coded."

Point at the footer/disclaimer, then go to **Window A**.

---

## 0:30–1:40 — Institution: what the portal tells you (Window A)

1. Sign in, land on **Welcome back**, open **Dashboard** in the sidebar
   (shortcut `g s`).
2. The stage track is on **Scrutiny** for `AICTE/2026-27/0000109` — Vidya Vikas
   College of Engineering (Fictional).
3. **What you need to do** shows, from live data:
   - **Documents expiring**: `fire_safety_certificate_expired.pdf`, 90 days
     past validity, `APH 6.17h`.
   - **Fees**: Total TER ₹1,00,000, Paid ₹1,00,000, Due ₹0 (APH Table 1.1).
   - **Compliance score** with the top failing rules and how to fix them.
   - **Statutory deadlines** for appeal and Security Deposit when a case has
     them.
4. Click **Open case file**.

### Case file — the part judges remember

5. **Documents** tab. Two flags are already there:
   - `fire_safety_certificate_expired.pdf` — **REJECTED**, reason `EXPIRED`,
     clause `APH 1.8f`.
   - `dsc_certificate_unsigned.pdf` — **FLAGGED**, reason `NO_DSC`,
     clause `APH 1.4.3`.
6. **Compliance** tab. Every row shows requirement, observed value, severity,
   status and **APH clause**. Five rules fail; two are CRITICAL. Open one row
   and read the explanation: criterion, observed value, threshold, pass/fail.
7. Scroll to **Deficiency Report** → **Generate report** → **Download PDF**.
   This is the document the officer will issue — generated from the same rule
   evaluation, with a *Nil Deficiency* banner only when every mandatory rule
   passes or is assessed.
8. **Fees** tab: receipt number, paid date, and the fee line's clause.

> "Notice the numbers agree: the dashboard's score, the case file gauge and the
> Deficiency Report all come from one rule evaluation."

*(Talking point, no clicks: the institution's own wizard is the eight-step
New/Extension form — Profile, Infrastructure, Faculty, Finance, Accreditation,
Programmes, Documents, Payment — with the same Deficiency Report preview on the
Review step before submission. It is demoed live in Appendix A if time allows.)*

---

## 1:40–2:25 — Regulation Bureau: automatic committee draw (Window B)

1. Sign in, **Applications**, open `AICTE/2026-27/0000109`.
2. **Committees** tab → **Constitute Committee**.
3. Keep **Scrutiny Committee (APH 16.3/16.4)**, mode **Online**, leave the seed
   blank, click **Run Automated Draw**.
4. The draw shows the selected members with their seat, the selection seed, and
   the exclusions applied — including the rule that an expert from the same
   state as the institution is skipped. Same seed ⇒ same committee, so the draw
   is reproducible for audit (`selection_seed`).
5. Point at the **Timeline** tab: every transition is a row with actor, action,
   from → to and clause.

> "Committee selection is deterministic and auditable; it is not a human
> shortlist. APH Annexure-16 defines the seats."

---

## 2:25–3:10 — Expert Visit video (Window D)

1. Sign in as `inspection@example.edu`, open `AICTE/2026-27/0000102`
   (MAH-0002, increase in intake, EVC constituted).
2. The only action offered is **Upload the EVC video** — because the role and
   the case state allow exactly that.
3. Enter `https://video.example.edu/evc-demo`, minutes `30` (the form rejects
   less than 30 — APH 1.9f-g), submit.
4. **Committees** tab shows the EVC composition; the inspection card shows the
   visit scheduled for 11 Nov 2026 and the pending structured report.

> "Role-scoped actions: the institution cannot upload its own visit video, and
> the EVC member cannot approve the case."

---

## 3:10–4:15 — Scrutiny: LoD drafted from failed rules (Window C)

1. Sign in as `scrutiny@example.edu`, open `AICTE/2026-27/0000109`.
2. **Compliance** tab. Hover the CRITICAL fire-certificate rule and click
   **Draft deficiency** — the dialog opens pre-filled with the rule's category
   and message.
3. Add a second deficiency with **Add another deficiency** (category
   *Documents*, e.g. "Upload the digitally signed DSC certificate, APH 2.3.4a")
   and set a due date 15 days out.
4. Submit. The action is **Communicate deficiencies (LoD)**: status moves
   `SCRUTINY → DEFICIENCY_COMMUNICATED` through the state machine, the
   institution is notified, and the deficiency timers start.
5. **Deficiencies and LoD** tab now lists the items with due dates and the
   clause on each.

> "The officer never types a rule; they draft from the evaluation. The clause
> and severity travel with the deficiency."

---

## 4:15–4:50 — Institution responds (Window A)

1. Refresh. The dashboard's **Open deficiencies** block counts the new items.
2. Open the case → **Deficiencies and LoD** → **Respond**.
3. Type a short response ("Valid fire safety certificate and signed DSC
   uploaded; see documents") and submit.
4. Status moves `DEFICIENCY_COMMUNICATED → INSTITUTION_COMPLIANCE`; the
   response is a workflow event and an audit row, and the scrutiny officer's
   queue gets it back.

---

## 4:50–6:10 — Time: statutory clocks expire and escalate (Window B)

1. Still as `regulation@example.edu`, click **Demo time** (top bar) → **Advance
   7 days**. The control replays the scheduler day by day: deadline warnings,
   then breaches, then escalations.
2. Open **Alerts**. Filter **Type → Appeal expired**: the seven seeded appeal
   windows (APH 1.11a, 7 days) have closed and the LoR stands. Each row shows
   the case, severity and recipient.
3. Filter **Type → Security Deposit overdue**: the deposit clock (APH 2.25f,
   15 days) has run out and the penalty ladder has started.
4. Clear the filters and look at **Escalation · level 1/2/3** rows: unacknowledged
   alerts climb the ladder, and the level is on the row.
5. Open one expired case, `AICTE/2026-27/0000003`, **Decision** and **Timeline**
   tabs: the appeal window card reads **1 day past**, the status is final, and
   the events show what the sweep did and when.

> "No cron job was hand-triggered and no status was set by hand: the clock moved,
> the scheduled scan ran, and the workflow sweep applied the transitions the
> handbook requires."

Reset for the next run with **Demo time → Reset to real time** (or restart the
backend) and `make reset-demo`.

---

## 6:10–6:50 — National oversight map (Window E)

1. Sign in as `admin@example.edu` → **Dashboard**.
2. The tile cartogram covers 60 fictional institutions across 10 states and all
   eight AICTE regions.
3. Toggle the metric: **Compliance RAG → SLA breaches → Pending applications →
   Penal actions**. Click a state to narrow the **Needs attention** list
   (ordered by non-GREEN institutions, then lowest average score).
4. The rest of the page is the same data cut differently: funnel, approvals vs
   rejections, appeals, Security Deposits, compliance histogram, top violation
   codes.

> "Aggregates are SQL over the same rows the case files use — no separate
> reporting store, no exported spreadsheets."

---

## 6:50–7:00 — Close

> "One state machine, one deadline service, one audit log. Rules, fees,
> thresholds and alert templates are configuration with a clause reference, so a
> new handbook cycle is a data change, not a rewrite."

---

## If you have extra time

| Beat | Where | Why it lands |
| ---- | ----- | ------------ |
| Live submission | Appendix A | The full wizard, payment and submission in one run |
| Security Deposit penalty | Window B, `AICTE/2026-27/0000104` | 20% penalty after the deposit window, `APH 2.25f` |
| Complaint → SHC | `AICTE/2026-27/0000107` (`institution7@example.edu`) | Anonymity rules, show-cause, hearing, penal action |
| Deficiency → LoR → appeal | `AICTE/2026-27/0000103` (`institution3@example.edu`) | A closed loop with the Re-Scrutiny and SAC |
| Hibernation / excess admission | `AICTE/2026-27/0000105`, `0000106` | Status and penal-action reporting |
| Audit trail | **Audit logs** (`g u`) | Before/after JSON for every write, with IP |

---

## Appendix A — Live submission (about 6 extra minutes)

Only run this when the audience asks to see the wizard. It needs 21 mandatory
uploads for a new institution, so the seeded case files are the fast path.

1. Window A → **Start application**.
2. Type **New technical institution (Chapter I)**; **Create draft**.
3. Walk the steps: Profile → Infrastructure → Faculty → Finance →
   Accreditation → Programmes → Documents → Payment. The rail shows what is
   missing; Save is automatic.
4. **Review** shows completeness, the predicted compliance and the
   **Deficiency Report** before anything is submitted.
5. **Payment**: **Pay ₹1,00,000** records the TER receipt (APH Table 1.1).
   Submission stays disabled until the receipt exists.
6. **Submit application**: status `DRAFT → SUBMITTED`, SLA set by
   `SLAConfig`, workflow event and audit row written.
7. Switch to Window B (**Applications → Submitted**): the case is in the
   Regulation Bureau queue; **Assign the Scrutiny Committee** moves it to
   `SCRUTINY`.

Date behaviour worth knowing: a submission after the seeded Public Notice
cut-off is flagged late, charged the late penalty (APH 2.3.2) and moved to the
next configured academic year instead of failing.

---

## Known gaps to state honestly

- Committee, inspection, risk and compliance figures are **illustrative**;
  thresholds must be verified against the current APH before real use.
- The seeded scenario institutions carry summary-level wizard data, so their
  compliance preview is dominated by unassessed document rules. The live case
  `0000109` carries the full document set and therefore the intended 45.71
  score.
- The regional aggregate report is not yet narrowed to a Regional Officer's
  own region; the national tile map is the Super Admin view.
- Email/SMS delivery uses Mailpit and a mock SMS provider; nothing leaves the
  machine.
