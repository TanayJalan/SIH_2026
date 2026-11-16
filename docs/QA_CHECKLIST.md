# QA checklist

Quality pass and five-part verification of the AICTE Approval Workflow prototype.
Run on 13–14 November 2026 against the local Docker Compose stack (project `sih20`),
Chromium only, at `http://localhost:5173` with the API at `http://localhost:8000`.

The repository is a detached `HEAD` at `3a9749d` plus the uncommitted quality-pass
changes listed in the final summary. Backend tests ran on a freshly reset demo seed.

## Reproduce

```bash
docker compose -p sih20 up -d
docker compose -p sih20 run --rm backend python -m app.reset_demo   # ~18–35 s
cd backend  && docker compose -p sih20 exec -T backend pytest -q     # 294 tests, ~3:34
cd frontend && npm run build                                         # type-check + bundle
cd frontend && npx playwright test e2e/*.spec.ts                     # 16 tests, ~7:20
```

`make reset-demo` is also documented, but the Make target starts a second Compose
project named after the directory and collides with Mailpit on port 1025 when the
`sih20` stack is already up. Use the explicit `-p sih20` form above in that case.

The ad-hoc Playwright walkthrough scripts used for the checks below were temporary and
have been deleted; their coverage is recorded here.

## 1. Buttons and forms for every role

Every control in the demo flow and the admin workspace was clicked or submitted;
mutating actions were performed on the demo database and the seed was reset afterwards.

| Area | Check | Result |
| --- | --- | --- |
| Sign-in | 10 demo accounts sign in with `ChangeMe123!`; account list expands and fills the form | PASS |
| Institution dashboard | KPI cards, stage track, "What you need to do", deadlines, compliance score, "Open case file" | PASS |
| Case file tabs | Overview, Documents, Compliance, Deficiencies and LoD, Committees, Fees, Decision, Complaints, Timeline | PASS |
| Deficiency report | `Generate report` then `Download PDF` returns a named PDF | PASS |
| Fees | Receipt, paid date, TER line and clause render | PASS |
| Document review | Reject/flag dialogs, version drawer, download | PASS (reviewer flows exercised by seed + e2e) |
| Document re-upload | File picker, DSC attestation, signer, validity, version 2, old version retained | PASS |
| Submit compliance | Response required per open deficiency; case moves to `INSTITUTION_COMPLIANCE` | PASS |
| Scrutiny | Draft deficiency pre-filled from failed rules; add a second item; `Communicate deficiencies (LoD)` | PASS |
| Committee draw | `Constitute Committee` → `Run Automated Draw` appends a constituted committee with seat, seed hash and quorum | PASS |
| EVC video | 10-minute video rejected ("at least 30 minutes"); 30-minute video accepted | PASS |
| Alerts | Acknowledge an alert; filter by status (`Acknowledged`) and by type | PASS |
| Alert rules | Create (T-11), edit name, delete; duplicate trigger+threshold is rejected with 409 | PASS |
| Compliance monitoring | `Re-evaluate now`; Scoring tab → `Save configuration`; scores and bands reload | PASS |
| Eligibility advisor | `/eligibility` shows the five route cards with green/amber/red pills, the value on record, required threshold and clause; `Start this application` opens `/applications/new?type=…` with the type preselected | PASS |
| Audit log | Entity-type filter, `Apply filters`, `Clear` | PASS |
| New application | Type + academic year → `Create draft`; wizard `Next`; autosave status | PASS |
| Profile / 404 | Profile identity and access scope; unknown route renders 404 | PASS |
| Permission denied | Institution → `/alert-rules`; scrutiny → `/applications/new` both render "Access denied" | PASS |
| Sign out | Account menu → Sign out returns to `/login` and removes the access token | PASS |
| Demo clock | Advance 7 days; filters show appeal-expired and Security Deposit overdue alerts; reset to real time | PASS |
| Dashboard metric | `SLA breaches` radio selects and recolours the map | PASS |
| Filters/refresh | Refresh and active-filter controls are intentional no-ops (no data change); verified manually | PASS |

Native validation observed: required fields on the reopen/withdraw dialogs, EVC 30-minute
minimum, DSC attestation and validity on re-upload, and the alert-rule uniqueness rule.

## 2. Clause audit against `docs/reference/APH_SPEC.md`

Method: extracted every `APH …` reference from `frontend/src`, `frontend/e2e`,
`backend/app`, `backend/seeds`, `backend/tests`, `docs/*.md` and `README.md`, then
resolved each against `APH_SPEC.md` plus the `APH_2024-27.txt` copy. References inside
`docs/reference/` and the historical Alembic migrations `0017`/`0018` are excluded.

- **0 unsupported citations** remain in the checked paths.
- Sub-letters lost by the PDF text extraction were collapsed to the nearest resolvable
  section (for example `1.8f` → `1.8`, `6.46a` → `6.46`); ranges are kept only when
  both endpoints resolve (`1.8-1.11`, `2.3.3d-e`).
- Clause labels that were hard-coded in UI text or service payloads now come from the
  row that produced the value (upcoming deadlines, dashboard headers).
- `required_documents` no longer cites the FAQ chapter: `TER_RECEIPT` → `APH 2.3.2`;
  `AFFIDAVIT_2` → `APH Annexure-1` (new/off-campus/closure-and-new), `APH 4.7.1`
  (university/deemed conversion), `APH Annexure-2.1` (other types).
- Thresholds, fees and calendar dates remain illustrative configuration, editable from
  the admin screens, and are labelled as such in the UI and README.

## 3. Demo accounts, reset and `DEMO_SCRIPT`

- All 10 accounts in `/public/stats` log in; the seeded password is `ChangeMe123!`.
- `python -m app.reset_demo` rebuilds 60 fictional institutions, 10 users and 5 cases
  in 18–35 s, then restarts the statutory timers.
- The full `docs/DEMO_SCRIPT.md` storyboard was walked end-to-end in one browser
  session, including role switching, and passed every step:
  institution dashboard → case flags → deficiency report → fees → committee draw →
  EVC video → LoD → re-upload → submit compliance → demo-clock sweep → alert filters →
  expired appeal decision → national dashboard → clock reset.
- The walkthrough exposed three real defects, all fixed:
  1. the institution dashboard returned HTTP 500 (`KeyError: apH_clause`) after the
     deadline clause was wired into the payload — the query now selects the column;
  2. a rejected `DSC_CERTIFICATE` row could not be replaced (HTTP 422) because the type
     is not in `required_documents` — an already-uploaded document is now replaceable
     even when the checklist no longer lists its type (regression test added);
  3. after a re-upload the case header did not refresh `allowed-actions`, so
     `Submit compliance` stayed hidden until a reload — the document mutation now
     invalidates that query.
- Step 9 of the script advances the demo clock by 7 days. Always run step 11
  (`Reset to real time`) or `reset-demo` before the next demo.

## 4. States, accessibility, responsiveness and performance

- Loading, empty, error and permission states exist on every page; `ErrorState` and
  retry actions were added where missing. The backend-unreachable state was observed
  during the dashboard defect above.
- Charts expose text summaries; tables and dialogs have accessible names; focus rings
  are present. `e2e/audit.spec.ts` runs axe on 13 routes for all 10 roles: no serious or
  critical findings.
- Role/route screenshots: 262 PNGs in `docs/screens/` (1440 and 390 widths). Tablet
  widths were reviewed during the layout pass but are not part of the saved set.
- Dashboards, overlays and chart libraries are lazy-loaded; shared chunks are gzip-served
  in production builds.
- Lighthouse, measured on a production build (`npm run build` + `vite preview` on
  `:5173`), authenticated, cold cache, Lighthouse 12 with the default mobile
  throttling and the desktop preset: **dashboard 91–92 mobile / 99 desktop; case file
  (AICTE/2026-27/0000109) 86–89 mobile / 99 desktop**. The case file's CLS fell from
  0.16–0.27 to 0.002–0.004 in this pass (details below).
- `npm run build` is clean (TypeScript + Vite).
- Case-file CLS regressions found and fixed in this pass, each re-measured: the anomaly
  flags block now sits below Case facts (it was inserted above them), the sidebar renders
  the risk panel first and mounts the panels below it only after the compliance read
  settles (a late list was pushing them ~500 px), the deadline strip renders only when the
  case actually has a statutory clock or deadline rows, and the stage placeholder reserves
  the height of the panel it replaces. Desktop CLS went from 0.21 to 0.006 and mobile from
  0.16–0.27 to 0.003.

## 5. Footer

The required sentence is visible on every authenticated screen and on the login screen:

> Prototype: fictional data; norms from AICTE APH 2024-27; dates are demo values.

The app footer appends: "Thresholds and fees are illustrative configuration and must be
verified against the current handbook."

## Automated results

| Check | Result |
| --- | --- |
| Backend `pytest -q` on a fresh seed | **331 passed** (21 deprecation/SQLAlchemy warnings only) |
| `make coverage` gate | **89.70%** total; `eligibility_advisor` 98% |
| `npm run build` | PASS |
| Playwright `e2e/*.spec.ts` (6 files) | **15 passed, 1 failed**; the one failure is the known `alert-live-update` cold-seed flake and passed immediately on retry (**16/16 effective**) |
| `docs/openapi.json` | Regenerated, 96 paths |
| Clause scanner | 0 unsupported references |
| DEMO_SCRIPT walkthrough (13 steps) | 13/13 PASS |
| Admin/account checks (10 steps) | 10/10 PASS |
| Playwright `audit.spec.ts` (10 roles × 13 routes × 2 widths) | **10/10 PASS**, no serious/critical axe findings, 262 screenshots refreshed |
| Lighthouse `dashboard` (production preview, cold cache) | mobile **91–92** (5 runs), desktop **99** (5 runs) |
| Lighthouse case file `AICTE/2026-27/0000109` | mobile **86–89** (most runs 87–88), desktop **99** (6 runs), CLS ≤ 0.007 |

## Known gaps and limitations (for Q&A)

1. **Case-file Lighthouse is 86–89 on mobile** (99 desktop), still under the 90 target.
   The remaining cost is the self-hosted webfont payload: the four latin faces are 96 kB,
   which on Lighthouse's throttled mobile profile competes with the 123 kB gzipped app
   bundle. A control build with the faces removed scored **89–91** with the same CLS, so
   the gap is bandwidth, not layout or scripting. Deferring the font request was tried and
   did not help (the stylesheet still blocks first paint, and `font-display: optional`
   means slow connections already render the fallback and would simply waste the bytes).
   Fixing it properly means cutting or dropping the brand faces, which is a design call.
2. **Illustrative data.** Every compliance threshold, fee, deadline, cut-off date and
   committee date is demo configuration and must be verified against the current AICTE
   Approval Process Handbook before any real decision. The footer says so.
3. **Citation granularity.** Where the PDF text extraction loses sub-letters, the UI
   cites the section rather than an unverifiable letter (see section 2). Ranges are
   validated endpoint-by-endpoint.
4. **`required_documents` is insert-only.** OQ-52's clause correction applies on
   `reset-demo`; an existing deployment needs a data migration.
5. **Known e2e flake.** `alert-live-update.spec.ts` can fail on the first run after a
   reset while the alert scanner warms up; it passes on retry. `officer-action.spec.ts`
   moves `AICTE/2026-27/0000109` out of Scrutiny, so reseed before rerunning it.
6. **Chromium only.** No Firefox/Safari or real-device pass; mobile was emulated at
   390 px. No screen-reader session (axe plus keyboard paths only).
7. **No tablet screenshot artifacts.** The saved matrix is 1440/390; 768/1024 were
   reviewed interactively.
8. **Scope.** The QA pass covers the demo's New/Extension deep flow and the admin
   configuration screens. Appeal, complaint, SHC/SAC and penal-action flows are covered
   by backend tests and route smoke checks, not by a full browser walkthrough.
9. **Notifications.** Email is delivered to Mailpit; SMS is a mock provider. No external
   provider was tested.
10. **Demo artifacts.** The seeded `DSC_CERTIFICATE` row exists in the documents list but
    not in `required_documents`; it is now replaceable, but the data mismatch remains a
    demo-only artifact.
11. **`make reset-demo` and the running stack.** The Make target creates a second Compose
    project and can collide on port 1025; use `-p sih20` when the stack is already up.
12. **OpenAPI contract.** `docs/openapi.json` is a snapshot, not a CI gate; regenerate it
    after route or schema changes.
13. **No automated visual regression.** Layout checks are the 262 screenshots plus axe;
    there is no pixel-diff baseline.
14. **Screenshots are untracked.** `docs/screens/` is about 21 MB of PNGs; decide whether
    to commit it or move it to Git LFS.
15. **Eligibility advisor scope.** The advisor reads the seeded (fictional) accreditation
    profile on the institution record; there is no data-entry screen yet for a real
    institution to supply those figures. TFW has no application type, and the
    working-professional route links to `INCREASE_INTAKE` because the portal has no
    dedicated type. Aspirational-district and J&K/Ladakh/NER status are stored as booleans,
    not derived from the current NITI Aayog or AICTE lists. See OQ-83 to OQ-89.
