# APH 2024-27 Domain Specification (extracted from the uploaded PDF)

Source: *AICTE Approval Process Handbook 2024-25 to 2026-27* (231 pages, read in full). Clause numbers (for example "APH 1.11a") refer to that handbook. Save this file as `docs/reference/APH_SPEC.md` in the repo, next to the PDF.

**How the handbook is organised:** Ch I new institution · Ch II existing institutions (extension of approval and changes) · Ch III collaboration/twinning · Ch IV universities · Ch V ODL/online · Ch VI norms · Ch VII penal action and complaints · Ch VIII dos and don'ts · Annexures 1-18 · Affidavits 1-13 · Formats 1-4 · Certificates 1-3.

**Not in the PDF (must be configurable):** actual cut-off dates (come from AICTE's Public Notice and Academic Calendar), processing-time limits for committees, and the portal's internal form fields. Anything marked ⚠ is ambiguous in the text (see section 12).

---

## 1. Actors, committees and roles (APH Annexure-16, Definitions)

| Actor | Role in the process | Composition / quorum (Annexure-16) |
|---|---|---|
| Applicant / Institution | Submits online, pays TER, uploads documents, responds to deficiencies, appeals | Two authorised representatives (Chairman/Secretary, or Principal/Director/faculty/trustee authorised) with self-attested photo ID attend Scrutiny, SHC, SAC (APH 1.8c, 1.11d, 2.24e) |
| Regulation Bureau | Intake, schedules committees, informs institutions, puts observations before committees, issues LoA/LoD/LoR and Speaking Orders | AICTE staff |
| Regional Office / Regional Officer | Constitutes the EVC (Definitions 29) | |
| Scrutiny / Re-Scrutiny Committee | Verifies authenticity of documents (Annexure 1/2). Members selected by an automated web-portal process (APH 1.8a) | **Chapter I:** Professor/Assoc. Professor of IIT/IIM/NIT/Govt institution + an advocate registered with Bar Council + an architect (or Prof/Assoc. Prof of Civil Structural). **Chapter II:** two Professors/Assoc. Professors of IIT/IIM/NIT/Govt institutions (16.3, 16.4) |
| Expert Visit Committee (EVC) | Online/physical verification of infrastructure, faculty, equipment, library; members selected by automated web-portal process (APH 1.9a) | Academician not below Professor from the EC-approved panel + expert not below Assoc. Prof or industry expert with 5+ years + architect (or CPWD/NBCC/DRDO/CSIR, or Prof/Assoc. Prof structural civil, or Asst Prof Architecture, or Prof/Assoc. Prof Planning). For deemed universities the chair is a VC/former VC/Director of IIT/NIT (16.5) |
| Standing Hearing Committee (SHC) | Assesses compliance of deficiencies from EVC reports and Show-Cause replies (16.8) | Chair: retired High Court judge, or educationist not below VC, or Director of IIT/NIT/IIM; one expert not below Assoc. Prof; one officer not below Deputy Director of Revenue / architect / Prof Civil / Prof Planning / land and revenue expert (16.6) |
| Standing Appellate Committee (SAC) | Hears appeals; can recommend, not recommend, or send back for Scrutiny/EVC | Same composition as SHC (16.6) |
| Standing Complaint Scrutiny Committee (SCSC) | Processes complaints | Retired High Court judge (chair) + two experts not below Assoc. Prof + architect/Prof Civil + DTE/Registrar. Quorum: any two members (16.7) |
| Executive Committee (EC) | Takes the approval decision; ratified by Council (1.10a) | Chairman, Vice-Chairman, Secretary MoE, etc.; quorum one third (16.2) |
| Council | Ratifies EC; final decision on appeals (1.11e) | 51 members (16.1) |
| PGRC (Public Grievance Redressal Cell) | Receives and processes complaints first (7.10b) | |
| Policy and Academic Planning Bureau | Concurrence for new course nomenclature (before 30 Nov); hearings for unapproved institutions (2.26e) | |
| Approval Bureau | Issues NOC for FDR release (6.46c) | |

Note: "Co-opt" rule: a State/UT/affiliating-university representative (not below Assoc. Prof) may be co-opted into Scrutiny/EVC/SHC/SAC (16 NOTE).

**Role mapping for the system:** INSTITUTION_ADMIN, REGULATION_BUREAU_OFFICER, SCRUTINY_COMMITTEE_MEMBER, EVC_MEMBER, REGIONAL_OFFICER, SHC_MEMBER, SAC_MEMBER, EXECUTIVE_COMMITTEE_MEMBER, COMPLAINT_SCRUTINY_MEMBER (SCSC), SUPER_ADMIN (Council secretariat).

---

## 2. Application types (Table 2.2 and 2.3)

**Category 1 (cut-off date in the Public Notice; later submissions are processed for the next academic year):** EoA on self-disclosure · NRI seats (intro/continuation) · conversion of Diploma↔Degree · change of name of institution or affiliating university/board or type · new programme/level · merger of institutions · EoA after break / restoration of intake / hibernation · supernumerary seats for FN/OCI/Gulf children · increase in intake / additional course · integrated/dual degree · off-campus · FPM · change of course name/merger of courses/reduction in intake · collaboration & twinning.

**Category 2 (year-round):** change of site/location · closure of institution · women↔co-ed conversion · closure of programme/course · change in bank details · change in name of trust/society/company · extended EoA · type of institution converted to deemed university · ODL/OL (processed twice a year as per UGC timeline).

**Steps per type (Table 2.3):** (Docs = Annexure-2 for all; AA = as applicable depending on earlier steps)

| Type | Self-Disclosure | Scrutiny/Re-Scrutiny | EVC | SHC/SAC |
|---|---|---|---|---|
| EoA based on Self-Disclosure | Yes | – | – (random EVC possible, 2.3.5a) | – |
| NRI seats | Yes | – | – | – |
| Diploma↔Degree conversion | – | Yes | Yes | AA |
| Change of name of institution / affiliating body / type | – | Yes | – | – |
| New programme/level | – | Yes | Yes | AA |
| Merger of institutions | – | Yes | Yes | AA |
| EoA after break / restoration / hibernation | – | Yes | Yes | AA |
| Supernumerary FN/OCI/Gulf | – | Yes | – | – |
| Increase in intake / additional course | – | Yes | Yes | AA |
| Integrated/dual degree | – | Yes | Yes | AA |
| Fellow Programme in Management | – | Yes | Yes | AA |
| Change of course name / merger of courses / reduction in intake | – | Yes | – | – |
| Collaboration and twinning | – | Yes | Yes | AA |
| Change of site/location | – | Yes | Yes | AA |
| Closure of institution | – | Yes | – | – |
| Women↔co-ed conversion | – | Yes | – | – |
| Closure of programme/course | – | Yes | – | – |
| Change in bank details | – | Yes | – | – |
| Change in name of trust/society/company | – | Yes | – | – |
| Type converted to deemed university | – | Yes | Yes | AA |
| ODL/OL courses | – | Yes | Yes | AA (processed twice a year) |

(The table's "Self-Disclosure" column shows "–" for many types because they go to scrutiny, but several of them still require "Nil Deficiency based on Self-Disclosure" in the clause text: 2.8a, 2.9, 2.10c, 2.12d, 3.2a. The portal's Deficiency Report should be generated for every type.)

Other new-institution variants (Chapter I): **1.3.2** new technical institution (E&T, Planning, Applied Arts & Crafts, Design, HMCT, Computer Applications, Management); **1.3.3** existing institutions approved by other regulators seeking AICTE approval for the first time (non-technical institutions running BCA/BBA/BMS/MCA/MBA, vocational/applied arts) — exclusive building and Director/Principal are not required for 1.3.3(b), but HoD, faculty, infrastructure and built-up area are; **1.5.2** closure plus new institution in same premises in same year (closure processed first; if rejected, closure or EoA as chosen).

**Universities (Chapter IV):** Category I/II universities (UGC graded autonomy) evaluated on NAAC certificate, government notification, UGC letters, Affidavit 2 and 5 (4.7.1). Others follow Chapter I/II. No partial approval allowed (4.4.3 note, 4.4.4b, 2.27). No conditional approval normally (4.9c). Institute of Eminence deemed universities exempt from annual approval but must update data and submit Affidavit 2 (AICTE) and 5 (UGC) (4.22).

**ODL/OL (Chapter V):** only PG certificate/diploma/degree in Management, Computer Applications, AI, Data Science, Cyber Security, Block Chain, Logistics, Travel & Tourism; not allowed for E&T, Planning, HMCT, Applied Arts, Design (5.1b). Eligibility: NIRF top-200 at least twice in three cycles, or NAAC 3.01+ with 5 years and 2 batches (and 3.26+ in next cycle), or standalone with NBA 700/1000, or NIRF top-200 (5.3.8). Headquarters staffing (Table 5.1: per discipline 1 Prof head, 1 Assoc Prof, 2 Asst Prof; Deputy Registrar 1, Asst Registrar 1, Section Officer 1, Assistants 3, Computer Operator 2, MTS 2), Learner Support Centre (Table 5.2: 1 Asst Prof coordinator, 2 counsellors per 4-credit theory course, 1 supervisor per 2-credit practical, 1 computer operator; up to 1000 students/centre), infrastructure (Table 5.3: HQ 1500 sqm; LSC 150 sqm; 300 Mbps), faculty:student 1:30 for project/assignment evaluation, admission twice a year (July and January), enrolment upload within one month of last admission date, one ODL course at a time per learner.

**Collaboration & twinning (Chapter III):** partner foreign university in top 1000 (QS/THE) or Indian partner with NAAC 3.01+/NBA 650+/NIRF top 200; max 40% credits from partner; one extra division; no lateral entry or supernumerary seats; annual report; NOC from affiliating body; MoU; Affidavit 11; TER Table 3.1.

---

## 3. Workflows

### 3.1 New institution (Chapter I, Annexure-7 flowchart verified)
1. Register on NSW portal → redirected to AICTE portal; user ID allotted on payment of ₹6,000 (1.4.1). Forgotten password: ₹6,000 + Affidavit 1.
2. Fill online application; edit allowed until final submission, then locked (1.4.3). All documents digitally signed with DSC; no DSC = no submission. Affidavit 2 (₹100 e-stamp, sworn). Copy of application to State Govt/UT and affiliating university/board with sealed receipt (1.4.5). Unique application number allotted; status trackable.
3. Pay TER charges by cut-off; unpaid = not considered (1.4.2e-f).
4. **Scrutiny Committee** (automated member selection; date/time informed by Regulation Bureau) → if deficiency: **Re-Scrutiny** (verifies only the listed deficiencies) → if nil deficiency: **EVC** (1.8). Annexure-7: scrutiny nil deficiency goes to EVC; EVC nil deficiency goes to EC; deficiency noted goes to EC.
5. **EVC** online/physical; institution uploads ≥30-minute video (entry/exit time, building plan signed by Scrutiny, GPS coordinates at entrance of main/academic/admin/library buildings) (1.9f-g). EVC checks only "Approved Intake" capacity, not admitted students (Ch VIII point 7).
6. Regulation Bureau observations → **Executive Committee** decides, **Council** ratifies → portal publishes **LoA**, **LoD** or **LoR** with Speaking Order (1.10). Letters issued on or before the Academic Calendar last date.
7. EC LoA cases go to Council; **LoR cases go to SAC** (Annexure-7). **Appeal** once, within **7 days** of LoD issue (1.11a), via portal, to SAC (appeal schedule on portal). SAC recommends, does not recommend, or sends back for SC/EVC; a second SAC then takes the final recommendation; the loop **repeats only once** (Annexure-7). Council's decision is final (1.11e).
8. LoA cases: Security Deposit + Affidavit 3 (1.12). Regional Committee endorsement of LoA/LoR appears in the flowchart.
9. LoA valid **2 academic years** for affiliation and state requirements; then it stands cancelled (1.10b ii). From next academic year the institution must apply for EoA regardless of admissions. An EVC may be held any time before the first batch passes out (1.10b 1). If no students admitted due to non-affiliation/state non-fulfilment: affidavit within **7 days** of intimation (1.10b i).
10. Faculty/Principal must be appointed before courses start (1.6d; Annexure-1 1.3.5).
11. TER refund: rejected at Scrutiny/Re-Scrutiny without appeal → refund minus ₹0.60 lakh (1.4.2h). Applicants rejected with final LoR the previous year pay reduced TER (Table 1.1 iii).

### 3.2 Existing institutions
- **EoA based on Self-Disclosure** (2.5): documents (Annexure-2.1) + online self-disclosure; Council grants based on self-disclosure, monitors fulfilment and takes penal action on non-fulfilment (2.5c). EVC at random (2.3.5a). False document = criminal case against Director/Principal and Chairman/Secretary (2.3.5b).
- **Deficiency report** available on the portal for submitted applications (2.3.3b). Institution gets a chance to comply before Scrutiny/Re-Scrutiny/SHC to reach "Nil Deficiency" (2.4). Deficiencies noted by SC/Re-SC/EVC must be fulfilled **before the EoA for next academic year is issued** (2.25c).
- **SHC** hearing for compliance (2.23.3) → EC → Speaking Order on portal → **appeal once within 7 days of decision upload** (2.24a) to SAC → Council final.
- Wrongly submitted application: represent to AICTE HQ with Trust resolution (Format 3) before the Public Notice last date; **reopened only once**, with TER and late penalty and competent-authority approval (2.3.3d-e). Revoking after TER payment (other than EoA): within 7 days of last date, refund minus ₹0.25 lakh (2.3.3f). Withdrawing a pending closure application by **10 April** (2.3.3g).
- EoA issued per academic year with **Approved Intake**; institution downloads the letter from its login after updating institutional information (2.25b,k). Decision lists placed before EC and ratified by Council (2.25a). **No EoA after the Academic Calendar last date** (2.25j). Enrolment details uploaded **before 30 November** (2.25n).
- **Extended EoA (3 years)** from AY 2024-25 for institutions meeting ANY ONE: figured in NIRF 8th edition; QS Asia 2024; ≥30% eligible courses with NBA valid till 30 Apr 2025; NAAC ≥3.01/4.0; autonomous status (UGC/AICTE); >80% admissions in each of last 5 academic years (2.1a). They still submit data annually. Standalone PGDM/PGCM institutions that never uploaded student details since AY 2018-19 cannot apply (2.3.1 note). Lease land: no EoA from the year when live lease equals the longest course duration unless lease extended by 30 years (2.1e).
- **Increase in intake / additional course** (2.6): upper limit on intake removed; subject to infrastructure, faculty (FSR) and documents; EVC mandatory; no increase while inquiries by Central/State agencies are pending; E&T needs ≥3 core branches; reduction in core branches limited (⚠ 2.6g says up to 50% of approved intake, not less than 30; 2.18a says up to 30 seats). Extra division for Indian-language courses (30/60 supernumerary) and an extra division of 15/30/60 for working professionals (institutions with >80% average enrolment in last 3 years, aspirational districts, J&K/Ladakh/NER) (2.6, 2.6l). Scrutiny and EVC for all increases; EVC any time before first batch passes out.
- **New programme/level** (2.7): applies along with EoA; multiple programmes allowed; if not approved, EoA is issued for existing.
- **NRI seats** (2.8): 5% of approved intake within approved intake; nil deficiency; merit by competent authority; vacant → general candidates at regular fee.
- **FN/OCI/Gulf-children supernumerary** (2.9): 15% over approved intake per course (1/3 for Gulf workers' children); eligibility: ≥80% average enrolment last three years; Study in India institutions exempt from EVC; hostel, international affairs office and counsellor required; FRRO registration; withdrawn if punitive action; apply per course each year.
- **Integrated/dual degree** (2.10): 5-year (E&T→M.Tech, Planning, HMCT), 4-year (computer applications→MCA, Management→MBA); nil deficiency.
- **Off-campus** (2.11): institution existing ≥10 years and meeting NIRF/QS/≥50% NBA courses/NAAC 3.01+/autonomy/>80% admissions for 5 years; within affiliating-university jurisdiction or same city; processed like a new institution; no student movement between campuses; infrastructure per Annexure-3.
- **FPM** (2.12, Annexure-15): MBA/MMS/PGDM existing; ≥50% faculty with PhD (20 seats) or 25% (10 seats); two Scopus/WoS papers in 3 years; Prof guides ≤6, Assoc Prof ≤4 scholars; duration 3–5 years.
- **Merger** (2.13): parent/child institution; same city; no intra-day movement of students/faculty; approved intake combined; affidavit that built-up area unchanged; women's institution converted to co-ed first; liabilities with trust; AICTE may reject if commercial angle suspected.
- **Diploma↔Degree conversion** (2.14): institution ≥5 years; same specialisation; all courses at level converted (no partial); progressive/complete closure of existing courses including PG in same discipline; no refund of excess security deposit when converting degree→diploma.
- **Women↔co-ed** (2.15), **break in EoA/hibernation/restoration** (2.16): not applied for **6 consecutive years** → must apply as new institution; hibernation period = one year less than longest course/level duration (e.g. 3 years for UG engineering, 1 year for PG management); EVC on return; punitive-action restoration must be sought next academic year and within 6 years (No Admission case); restoration after punitive action is applied for with next year's EoA (7.11a).
- **Change of site** (2.17): within current affiliating-university jurisdiction (PGDM exempt); movable property shifted only after approval; second EVC before session start; no partial shifting; violation = withdrawal of approval.
- **Change of course name / merge / reduce / close** (2.18): name change only where university does not offer nomenclature (Annexure 6/7 reference ⚠); closure not approved → EoA with **ZERO intake**; closure application valid for the course duration.
- **Change of name** of institution/affiliating body/type (2.19): follow name rules 1.5.4-1.5.5; university views due within 15 days of last date.
- **Change of trust/society/company name or address** (2.20): not for disqualified bodies; AICTE can lien the FDR during disputes.
- **Closure** (2.21): no TER; progressive (first year closed now; final order after programme completion and Affidavit 4) or complete; NoC subject to no pending court case/charge sheet; failed closure → EoA with zero intake; lapsed closure application → AICTE may close with **10%** penalty on deposit release; no EoA application for **6 years** → AICTE may close with **50%** penalty.
- **Unapproved institutions** (2.26, 7.2): public list; treated as new institution; legal start date = LoA date; no partial approval (2.27).

### 3.3 Complaints (7.10)
Complaint → PGRC → verified complaint to **SCSC** → warning, show-cause notice, or EVC through Regulation Bureau → report/replies to **SHC** (two representatives with photo ID appear) → **EC** → detailed Speaking Order on portal → appeal under 1.11/2.23. **Anonymous or pseudonymous complaints are not processed** (CVC guideline). Institutions upload complaint counts and actions on website and in a **monthly online status report** (7.13). Fake SC/ST/OBC/EWS/PwD certificate complaints investigated in time-bound manner; admission cancelled if guilty (7.8).

### 3.4 Restoration after punitive action (7.11, 7.12)
Application with next year's EoA → SC/EVC as applicable → EVC report to SHC → EC → appeal to SAC → Council; EoA with restored intake or Speaking Order. If approved after **30 April**, implemented only next academic year (Supreme Court order, 7.12).

### 3.5 Release of Security Deposit (6.46)
Request letter, Affidavit 6, FDR/RPGF/demand-draft/online payment proof, latest LoA/EoA; clearance from PGRC, Vigilance and other bureaus; NOC for FDR (Approval Bureau) or sanction order for RTGS; withheld if financial embezzlement; progressive closure needs a university certificate that no students remain; merger releases child institution deposit similarly; conversion to private university needs no pending complaints.

---

## 4. Fees, deposits and penalties (rupees in lakh unless stated)

**Common rules:** payment only online through the portal gateway; no demand drafts; unpaid by cut-off = not considered; 10% annual increase in TER; TER not refunded once application is processed and rejected (except as stated); excess payment is refunded, not adjusted (Ch VIII 8-10).

**New institution TER (Table 1.1):** Government / J&K / Ladakh / North East / PwBD / exclusively women = **1.00**; all others (including minority and govt-aided) = **10.00**; previous-year final-LoR applicants: Govt **0.25**, others **1.00**. User ID ₹6,000.

**Existing institutions (Table 2.1)** (Govt/Central University/State University | All others):

| Item | Govt | Others |
|---|---|---|
| EoA on self-disclosure per division, all programmes except PGDM/MBA | 0.05 | 0.20 |
| EoA per division PGDM/MBA | 0.15 | 0.40 |
| Vocational courses | Nil | Nil |
| Late submission penalty | 0.25 | 2.50 |
| Break in EoA / restoration of intake | 0.50 | 2.50 |
| Introduction of OCI/FN/Gulf seats / off-campus | 0.50 | 6.00 |
| Continuation of OCI/FN/Gulf seats per course | 0.05 | 0.30 |
| Introduction of Fellow Programme in Management | 0.50 | 1.25 |
| Change of site; Diploma↔Degree; new programme/level; change of trust name; merger | 0.25 | 3.50 |
| Degree↔Diploma; women↔co-ed; NRI seats; increase in intake/additional course; integrated/dual degree | 0.15 | 1.25 |
| Change of course name/merger/reduction/closure of programme; change of institution/affiliating body/type name; trust address | 0.10 | 0.60 |
| Change in bank details | 0.06 (₹6,000) | 0.06 |
| Closure of institution | No TER | No TER |

Notes: EoA and OCI-continuation TER depend on number of divisions/courses of the applied intake; other items are flat. No TER for PG degree courses other than MCA/management and for hibernation. Extra SC/SHC/SAC (court directions included) = 0.60 (Govt 0.15); extra EVC = 1.25 online / 2.50 physical (Govt 0.25 / 0.50). Rejected at scrutiny without appeal (type list in 2.3.2e) → refund minus 0.60. Revoked after payment → refund minus 0.25 (2.3.3f).

**Collaboration/twinning (Table 3.1):** introduction 2.0 (Govt-type) / 12.0 (others); continuation 1.0 / 6.0.
**Universities (Table 4.1):** Govt-type 2.00; private 10.00; previous-year final LoR: 1.00 / 4.00; separate TER per campus (main/off).
**ODL/OL (Table 5.5):** new ODL HQ + up to 2 LSC (intake ≤5000) 10.00; new application by existing approved institution 1.25; each additional LSC (≤1000) 3.50 (ODL only); EoA (≤1000) 2.00; new course/increase per 1000 seats 2.50; previous-year LoR 2.50; closure/reduction/rename 0.25 per LSC/HQ. Extra scrutiny 1.0, extra EVC 2.0, extra SHC/SAC 1.0. Rejected at scrutiny → refund minus ₹60,000.
**NOC to run other regulators' courses** (6.30): ₹0.60 lakh and Affidavit 12.

**Fund position required for a new institute at scrutiny (Table 1.2):** Engineering and Technology 100; Planning, Applied Arts & Crafts, Design, HMCT, Computer Applications, Management 50 (FDR/bank account in a nationalised or scheduled commercial bank). Govt/aided/Central/State university: budget provision of at least ₹100 lakh plus land/built-up area (1.5.3).

**Security Deposit (Table 1.4; held 10 years):** E&T Diploma 15 / UG 35 / PG 15; Planning, Applied Arts, Design, HMCT: 15 each level; Computer Applications UG 5 / PG 15; Management UG 5 / PG 15. **Doubled** for private leased building or land. Exempt: Government/aided; existing institutions under 1.3.3 with >5 years at another regulator; Private universities existing >10 years with UGC; Central/State/Govt deemed universities (4.10). Deposit proof + Affidavit 3 within **15 days** of intimation, else **10%** (up to 31 May) or **20%** (up to 31 July) penalty; beyond that approval is withdrawn (2.25f). Early encashment or not depositing at LoA = **10%** of FDR (7.7). Interest used by AICTE; principal returned after term; extension or forfeiture for violations (1.12, 2.25g-h).

**Penal fine:** five times the total course fee per excess admission (7.3g).

---

## 5. Deadlines and time rules (everything dated or time-bound in the PDF)

| Rule | Value | Clause |
|---|---|---|
| Submission and payment | Public Notice cut-off; late = next academic year | 1.2, 2.2, Table 2.2 |
| Appeal after LoD / decision upload | 7 days | 1.11a, 2.24a |
| Security Deposit proof + Affidavit 3 | 15 days from intimation; penalties to 31 May (10%) and 31 July (20%) | 2.25f |
| Affidavit when no admission due to non-affiliation | 7 days from intimation | 1.10b i |
| LoA validity | 2 academic years | 1.10b ii |
| Revoke application after payment | within 7 days of last date | 2.3.3f |
| Withdraw pending closure application | on or before 10 April | 2.3.3g |
| Affiliating-body views on name change | within 15 days of last date | 2.19c |
| Restoration/punitive action approved after | 30 April → next academic year | 7.12 |
| Student enrolment upload | before 30 November (ODL/PGDM: within one month of last admission date; universities: Academic Calendar date) | 2.25n, 4.18, 5.3.6, Annex 6 6.8 |
| New course nomenclature concurrence | before 30 November | 5.3.11, 6.7a |
| IC annual report upload | by 30 June | 6.48g |
| PGDM admission window | 1 March to 30 June; withdrawal refund last date 30 June; session 1 July–30 June | Annex 6 |
| Faculty ID add/remove on portal | same month as joining/leaving | 6.14c |
| Fee refund after withdrawal | within 7 days | 6.45 |
| Student grievance: SGRC report | 15 days; Ombudsperson appeal 15 days; Ombudsperson resolves within 30 days; online portal reference within 15 days | 6.50 |
| Principal/Director vacancy | penal action beyond 12 months | 7.4b |
| Faculty pay/qualification/FSR shortfall | penal action beyond 12 months | 7.4c |
| Structural Stability Certificate | required after 30 years from completion; valid 5 years | 6.17h |
| Partial/provisional Occupancy Certificate | accepted for 2 consecutive academic years only | Annex 3 3.1c |
| Hibernation | one year less than longest course duration | 2.16.1d |
| No EoA application | 6 consecutive years → apply as new / AICTE may close | 2.16.1a, 2.21i |
| Reduced-enrolment rule | <30% of intake for preceding 5 years and next year ≤50% → intake cut 50%; auto-restored when enrolment >30% | 6.12a |
| Poor academic performance | warning, 2 years to improve | 6.12b |
| After withdrawal of approval | reapply only after 2 academic years with a different name | 7.1b |
| Twinning withdrawal | no new collaboration for 3 years | 7.5d |
| Complaints/grievances report | monthly online status report | 7.13 |
| Fellow programme marks sheet | 30 September; final deadline 31 December | Annex 15 |
| Library hours (desirable) | 16 h working days, 12 h non-working days | Annex 4 |
| Lateral entry | ≤10% of approved intake, supernumerary | 6.13a |

---

## 6. Eligibility and structural rules

- **Promoter (1.3.4):** registered Society, registered Trust, Section 8 company, or Central/State/UT government (also PPP/BOT through authorised officer). No foreign equity in a company (exceptions by Government). Section 8 company MoA must state non-profit objective.
- **Naming (1.5.4-1.5.6, 2.19b):** no abbreviation resembling IIM/IIT/IISc/NIT/IISER/IIIT/IIEST/AICTE/UGC/MoE/GoI; no "Government/India/Indian/National/All India/All India Council/Commission" for private institutions; no duplicating names within a State (add town/village); same font and size everywhere.
- **Head of institution:** Principal/Director with AICTE-prescribed qualifications; for a multi-programme institution qualifications correspond to the programme with the largest approved intake (2.7j, 2.13o).
- **Programme composition (1.7.1):** E&T new institution starts with ≥4 courses: ≥3 core branches + 1 emerging. State/Central universities offering only PG E&T: max 5 courses unless NBA-valid.
- **Maximum intake for new institutions (Table 1.3)** (intake per division, max courses, max divisions, max intake): E&T Diploma 60/30, 6, 6, 360; UG 60/30, 6, 6, 360; PG 30 (min 6 steps of 6), 5, 5, 150. Applied Arts & Crafts: 30, 3, 3, 90 (all levels). Design: Diploma 30, 3, 3, 90; UG 30, 5, 5, 150; PG 15, 3, 3, 45. HMCT: Diploma 60, 3, 3, 180; UG 60, 3, 3, 180; PG 30, 3, 3, 90. Computer Applications: UG 60/30, 5, 5, 300; PG 60, 5, 5, 300. Management: UG 60/30, 5, 5, 300; PG 60, 6, 6, 360. Planning: UG 40, 3, 1, 120; PG 30, 1, 1, 30. For existing institutions the upper limit has been removed subject to infrastructure and faculty verified by EVC (Foreword, 2.6). One collaboration/twinning division is allowed per course.
- **Division sizes (Definitions 26):** E&T Diploma/UG 60 or 30; HMCT Diploma/UG, MCA/Management PG 60; UG computer/management 60 or 30; Planning Diploma/UG 40; Applied Arts & Design Diploma/UG 30; PG E&T/Planning/Applied Arts/HMCT 30; PG Design 15; Integrated 60 (Planning 40); FPM max 20 seats per year.
- **Seat categories (supernumerary unless stated):** NRI 5% *within* approved intake (2.8b); FN/OCI/Gulf 15% over approved intake (2.9); lateral entry ≤10% (6.13); Tuition Fee Waiver up to 5% per course, only where ≥50% of approved intake filled last year, parental income ≤₹8 lakh, mandatory (6.42); PM-USPY J&K/Ladakh 2 per course (max 10 per institution) (6.43); Gifted children 2 per institution (6.44); PwBD polytechnics 25 (6.38a); Kashmiri migrants (6.38b); EWS 10% reservation with intake raised 1.25× (6.37); working-professional extra division; regional-language extra division. FN + lateral entry of foreign nationals together ≤15% (6.13b).
- **Regular mode:** regular shift and flexible-timing classes count as regular; the full approved intake infrastructure/faculty needed (6.5, 6.10). 40% of courses may be through SWAYAM/MOOCs (6.11). Affiliation with two universities for the same technical course not permitted (except computer applications and management) (2.6 note 2).
- **Fee:** as fixed by State Fee Regulatory Committee; no capitation or donations (6.34-6.35); excess fee must be refunded and is penalised (7.4i). Refund policy: ≤₹1000 processing fee, certificates returned in 7 days (6.45).

---

## 7. Compliance norms (rules to encode)

### 7.1 Faculty (Annexure-5, 6.14)
- S = sum of approved intake across all years of the programme (Diploma: all years; UG: 4 years etc.). Required faculty = S / ratio.
- **Faculty:Student ratio:** Diploma 1:25 (E&T, Applied Arts, Design, HMCT); UG: E&T 1:20, Planning 1:16, Applied Arts & Crafts 1:15, Design 1:15, HMCT 1:20, Computer Applications 1:25, Management 1:25; PG: E&T 1:15, Planning 1:10, Applied Arts 1:15, Design 1:15, HMCT 1:12, MCA 1:20, MBA/PGDM 1:20. Integrated Planning: 1:16 first three years, 1:10 next two.
- **Diploma:** Principal/Director 1; Head of Department 1 per department; faculty = S/25 − 1; total S/25.
- **UG/PG cadre:** Principal/Director 1 (UG; none counted for PG except MCA/MBA); then Professor : Associate : Assistant = **1 : 2 : 6** (R = 9) for UG and for MCA/MBA/PGDM (footnote #); the PG table footnote marks PG E&T and PG HMCT with R = (1+1+1) = 3 (footnote *), while PG Planning, Applied Arts and Design carry no footnote (⚠ see section 12). Cadre ratio 1:2:6 is stated as general and not applicable at Diploma level. Qualified Associate Professor may substitute if no qualified Professor.
- **Reduction:** if average admission over last 3 years ≤50% of average sanctioned intake, faculty requirement is reduced by **25%**.
- Adjunct faculty / Professor of Practice: up to **15%** of required faculty; Professors of Practice not less than **10%**; Design up to 20%; Planning up to 30%; Assistant/Associate Professors of Practice need 5 / 8 years of industry experience (6.14d).
- Every PG course needs at least one Professor with PhD (or Associate Professor with PhD if none) (6.14f).
- Regular faculty required; contractual only briefly in extraordinary cases (6.14e). Salary through ECS via nationalised banks (6.14a); biometric attendance (6.14j); Aadhaar/PAN seeding (6.14i); IDs updated on portal in same month (6.14c); no retention of original degree certificates (6.14b, 7.4k); appointments in format uploaded to portal (1.6c).
- Salary sheet (pay scale, gross pay, PF, TDS) for closure/FSR proof (Annexure 1.4.3, 2.7ii).

### 7.2 Land, building and area (Annexure-3, 6.17-6.18)
- Land: clear title in the name of the promoter, or lease ≥30 years with live lease ≥ longest course duration (6.17a; Annexure-1 requires at least 5 years live lease and Joint Affidavit 7). Contiguous plots; max **three plots**, academic/instructional/admin/amenities in one plot, plots ≤**2 km** apart (hilly/NER regions 3 pieces ≤2 km); no obstacles (river, canal, rail, highway, high-tension lines) (6.17d, Annex 3 3.1g-h). Land use/conversion certificate; registered building plan by a registered architect approved by the competent authority (state-wise authorities in Annexure-14).
- Built-up area = (Instructional + Administrative + Amenities carpet area) + **Access and Circulation Area ≈ 25%** (Annex 3 3.2).
- **Instructional area for E&T:** class rooms = divisions per year × course duration (years) × 0.5, 66 sqm (division of 60) or 33 sqm (30); tutorial rooms = 25% of classrooms, 33 sqm; 4 first-year labs (incl. 2 basic science) 66 sqm up to intake 600; 2 labs per course per year (up to intake 180) 66 sqm; PG lab 1 per course 66 sqm, 1 research lab 66 sqm; workshop 200 sqm (1 up to 600, +1 for 601–1200); additional workshop for "X" category courses (Mechanical, Production, Civil, Electrical, Chemical, Textile, Marine, Aeronautical and allied) 200 sqm UG / 150 Diploma; CAD/drawing hall 132 sqm; computer centre 150 sqm; seminar hall 132; library 400 sqm; language lab 33 sqm; up to 50% of labs shareable for allied branches; extra labs pro rata for more than 3 divisions; intake above 1200 pro rata.
- Other programmes' instructional area (Annexure 3 3.2.1 B–G): Planning, Applied Arts & Crafts, Design, HMCT, Computer Applications, Management (rooms and sizes as in the handbook; seed them as data).
- **Administrative area:** minimum 750 sqm for intake up to 300; **Amenities:** minimum 500 sqm for intake up to 300. Library +50 sqm per 60 students beyond intake 420. Desirable 1.1 sqm per student for class and tutorial rooms. One smart classroom per course (min), MOOCs centre and innovation/fab/tinkering lab.
- Occupancy/Completion Certificate/Building License/Form D; Structural Stability Certificate (30-year rule, 5-year validity); Fire Safety Certificate; barrier-free environment (CPWD/NBC); playground owned or hired (6.31); high-tension line undertaking/certificate; excess built-up area may be used for hostel, research park, incubator (6.18) or other courses with building-plan amendment (6.29).

### 7.3 Library, computing, internet, laboratories (Annexure-4)
- **PC:Student ratio (min 20 PCs):** E&T Diploma 1:10, UG 1:10, PG 1:4; Planning UG 1:6, PG 1:4; Applied Arts Diploma/UG 1:6, PG 1:4; Design UG 1:6, PG 1:4; HMCT Diploma/UG 1:6; Computer Applications UG 1:10, PG 1:4; Management UG 1:10, PG 1:6. Printers ≥5% of PCs; A1 colour plotter for Planning; each department has a computer lab of ≥20 computers; plagiarism-checking software; LAN/Wi-Fi; exclusive systems for library/admin/faculty. Language lab ≥20 computers (20 per 300 intake, pro rata).
- **Internet bandwidth:** intake ≤300: 100 Mbps; 301–600: 300 Mbps; 601–900: 500 Mbps; >900: 1 Gbps.
- **Books:** B = number of divisions in first year; E&T UG: 100 titles in first year (volumes 5 × titles × B), +50 titles per year from year 2; Diploma 50; Management/Computer Applications 50 per year; Planning/Applied Arts/Design/HMCT 100 first year then 50; PG: 50 titles per course (4 × titles × B), MCA/MBA/PGDM 100 then 50; reading-room seating 15% of students (max 150) for UG/Diploma and 25% (max 100) for PG; up to 66% e-books; multimedia PCs for digital library 10% of students (max 30); NDL membership; stock increases for 10 years and then older editions replaced by 5%.
- **Journals:** subscribed, indexed (Scopus/Web of Science/Medline): UG and PG programmes 6 × N per level (N = number of courses); Diploma: adequate journals/periodicals.
- Lab equipment per affiliating university/board curriculum (Annexure-4.2); stock registers checked by EVC (1.9e).

### 7.4 Essential requirements (6.47-6.53) — each is a yes/no compliance flag with evidence
Anti-Ragging Committee, squad and cell with CCTV, workshops, helpline displayed, online undertaking (6.47) · Internal Committee for sexual harassment with prescribed composition and annual report by 30 June (6.48) · SC/ST committee (5 members, ≥2 SC/ST, ≥1 woman) (6.49) · online grievance redressal, Student Grievance Redressal Committee, faculty grievance cell, Ombudsperson (6.50) · Institution's Innovation Council with certificate and registration number (6.51) · barrier-free facilities (6.52) · Academic Bank of Credit compliance (standalone/PGDM/universities) · campus safety and security · Food Safety and Standards Act · digital payments only · display of all AICTE letters (LoA/EoA since inception) and accreditation status/BoG on the website · mental-health counselling platform · 24×7 women helpline · first aid and medical · potable water · waste management and green campus · student safety insurance and group accident policy for employees · social and emotional learning mechanism · compulsory internship for final-year students (affidavit on Internship Policy) · SWAYAM electives · skilling credits · industry-institution cell · language lab · IQAC (affidavit at EVC for new institutions). Undertakings: UHV induction-trained faculty (one per 20 new students), exam reforms. Documents must be uploaded **before downloading EoA**; the Council may verify at any time (6.53 note). Desirable (6.54): induction programme, one student one laptop, NITTT pedagogy training, NDL membership, SWAYAM access, FabLab/IDEA lab, one smart classroom per department, solar rooftop, general insurance, green campus, sanitary-napkin vending/incinerator, rainwater harvesting.
- **Board of Governors/Management** (Annexure-17): at least 11 and at most 21 members; trust nominates six including chairman and member secretary; plus affiliating-university nominee (AICTE nominee for PGDM), State Government nominee, a regional industrialist/educationist, Principal/Director as member secretary, two regular faculty (one Professor, one Associate/Assistant); minutes uploaded periodically.
- **Mandatory disclosure (Annexure-18)** (website + brochure + single PDF with LoA/EoA history, URL in portal attachments tab, free public access, dynamically updated): institution, trust and trustees, head profile, affiliating university; governance (org chart, grievance mechanisms, anti-ragging, IC, SC/ST committee, IQAC, equal opportunity cell); programmes (approved, NBA-accredited, seats, duration, cut-offs, fees, twinning details); faculty lists, permanent/adjunct, ratio, and profiles (name, DOB, unique ID, qualifications, experience, publications, patents, projects); fee waivers and scholarships; admissions (sanctioned seats, category-wise admitted for 3 years, management-quota applications), admission procedure, calendar and weightages, applicant lists and results; infrastructure inventory (rooms, labs, computer centres, examination facility, barrier-free, fire certificate, hostel, library, journals, NDL, equipment, innovation cell, social media cell, ABC, sports, short video of infrastructure); enrolment and placement for 3 years; research/consultancy projects; industry MoUs. Misrepresentation invites penal action.

---

## 8. Documents catalogue

**Always:** Affidavit 2 (digitally signed, ₹100 e-stamp, sworn before First Class Judicial Magistrate/Notary/Oath Commissioner; portal-generated common affidavit; contains 33 declarations: true information, location approved, OC/Structural/Fire certificates uploaded, other institutions in campus, regular qualified Principal, faculty norms and FSR, no retained original certificates, no admission without approval, digital payments only, sports facilities, IQAC and committees constituted, IC annual report uploaded, labour-law and minimum-wage compliance) · TER payment receipt · all uploads digitally signed (DSC).

**New institution (Annexure-1):** At Scrutiny: building plan (architect-certified, competent-authority approved; two copies) · Affidavit 2 · Trust resolution (Format 3) · Occupancy/Completion Certificate or affidavit to produce on completion · Fire Safety Certificate · bank manager certificate (Certificate 3) · application hard copy · trust/society/company registration documents with MoA · BoG composition (standalone PGDM) · Section 8 MoA non-profit clause · PPP/BOT resolution · land documents (registered sale/settlement/gift/lease deeds; ≥30-year lease; Joint Affidavit 7; notarised English translation) · private lease land/building document sets (lease deed, land conversion, title, encumbrance certificate, resolution, no mortgage; building plan, occupancy, fire, land-use certificate, floor plans, architect table of rooms/carpet areas) · working-capital proof per Table 1.2 · audited accounts for 3 years · minority certificate · Detailed Project Report · no high-tension line undertaking · Government building older than 50 years: competent-authority letter. Section 8 company documents: registration, MoA/AoA, incorporation, registered office, directors, PAN, TAN, general rules/forms, NOC from directors/promoters, 3-year audited statement. **At EVC:** advertisement for Principal/faculty in a national daily · internet bandwidth proof · book list with volumes · invoices for equipment and books · journal subscriptions · electrical load sanction · architect certificate on sewage, barrier-free, toilets, motorable roads · details of other institutions run by the trust · ~30-minute video uploaded to YouTube and linked. **After LoA:** faculty/Principal appointments uploaded; no course starts without all faculty and staff.

**Existing institutions (Annexure-2.1, EoA self-disclosure/break/restoration):** Affidavit 2 · portal pay-receipt print · valid Occupancy/Completion Certificate/Building License/Form D · Structural Stability Certificate (building >30 years) · valid Fire Safety Certificate · satellite map with latitude/longitude at main entrance · audited statement of accounts of previous year. Additional sets per type: NRI (resolution Format 3) · site change/women-coed/diploma-degree/new programme (Annexure-1 for site change, affiliating-body NOC Format 2, resolution) · merger (Annexure-2 set, NOC, resolution, legal merger documents) · FN/OCI (hostel details, international affairs office, resolution) · increase in intake/additional course/regional language/integrated/FPM (Affidavit 8, PhD faculty proof for FPM, resolution with land/funds allocation) · closure (NOC with alternative arrangements, salary sheet and FSR, RPGF/FDR details, student status, faculty/staff status and liabilities, Affidavit 4, pending court/ragging cases, resolution) · type change to university (Affidavit 2, NOC, resolution) · course rename/merge/reduction/closure (NOC, resolution) · institution name change (NOC or sealed receipt, resolution) · affiliating-body name change · bank details (Affidavit 9, resolution, bank-merger NOC) · trust name/address (registrar approval, Affidavit 10, registration document, BoG, Section 8 clause, land documents in new name, transfer deeds, working capital proof, trustee-change approval, resolution) · twinning (foreign recognition letter, fee/intake letters, admission guidelines, semester details, MoUs, Affidavit 11, proof of similar degree, NBA/NIRF certificate, resolution) · MBA/PGDM IEV (AICTE website format; special scrutiny committee at HQ).

**Affidavits:** 1 password · 2 main declaration · 3 Security Deposit · 4 closure · 5 universities (UGC) · 6 release of Security Deposit · 7 transfer of private property/building (lessor/lessee, irrevocable 30-year lease) · 8 additional course/intake · 9 bank details · 10 trust name/address · 11 twinning · 12 other regulators' courses · 13 ODL/OL. **Formats:** 1 NOC from State Government/UT · 2 NOC from affiliating university/board · 3 Trust resolution · 4 MoU with skill knowledge providers (NSQF). **Certificates:** 1 advocate (documents authentic; OC/structural certificates verified) · 2 architect (site/building plans authentic) · 3 bank manager (bank statement/FDR authentic, no loan/mortgage on FDR). **Undertaking (Annexure-10):** induction programme, exam reforms, internship policy, IIC, faculty details uploaded.

---

## 9. Penal actions (Chapter VII)
**Actions (7.3):** suspension of NRI/supernumerary seats for one year · reduction in approved intake · no admission in one or more courses for a year · withdrawal of programme approval · withdrawal of graded autonomy · withdrawal of institution approval · fine of five times total course fee per excess admission · ineligibility for AICTE grants. Withdrawal of approval of an institution: students redistributed by State/UT (7.1c); public notice for unapproved institutions (7.2).
**Violations (7.4):** false/incomplete/missing information in the EoA application (a) · Principal/Director vacant >12 months (b) · FSR, pay-scale or qualification shortfall >12 months (c; PGDM through AICTE committee) · shortfall in computers, software, labs, books, journals, library (d) · essential requirements not met (e) · temporary/unapproved location or insufficient built-up area (f) · excess admission (g) · admission eligibility violations incl. improper lateral transfers (h) · excess fee (i) · refusing EVC access or no OC/CC/Form D/barrier-free environment (j) · demanding original degree certificates (k) · deemed universities without ABC registration (l) · PGDM norm violations, no ABC, enrolment data not uploaded (m) · running partial-approval programmes or integrated/dual programmes needing multiple regulators (n). Also: fee-refund guideline violations (7.6), early FDR encashment/no deposit: 10% (7.7), no complaint/grievance monthly report (7.13), non-compliance with ombudsperson/SGRC recommendations (6.50h: withdrawal of approval, grants withheld, public notice, withdrawal of affiliation recommendation), twinning violations (7.5: withdrawal, MEA/MHA/RBI informed, 3-year bar).
**Process:** hearing before action (6.50h proviso), speaking order, appeal. Penalties paid online (7.9). Litigation: apply per 7.11 absent contrary court order (6.40).

---

## 10. Master data to seed
- **Programmes and levels:** Engineering & Technology, Planning, Applied Arts & Crafts, Design, HMCT, Computer Applications (BCA/MCA), Management (BBA/BMS/MBA/PGDM/PGCM), Pharmacy/Architecture (referred by definition), Vocational/NSQF. Levels: Diploma, Post Diploma Certificate, UG, PG Certificate, PG Diploma, PG Degree, Integrated/Dual, FPM.
- **Duration/eligibility (Annexure-8):** UG 4 years (BCA/BBA 3/4); PGDM 2 years (18 months for working professionals with 3 years' experience); PGCM 1 year; admission eligibility e.g. UG E&T 45% (40% reserved) in PCM/related subjects; PG 50% (45% reserved); NCrF levels 3.0–7.0+.
- **Annexure-11 nomenclature:** approved course names per level (Diploma ~390 entries, UG E&T, PG E&T, Planning, Applied Arts, Design, HMCT, etc.); core branches: Agriculture, Automobile, Chemical, Civil, Computer Science, Electrical and Electronics, Electronics and Communication, Electronics and Telecommunication, Food Technology, Industrial, Electronics Instrumentation, Mechanical, Metallurgy, Mining, Textile, etc.; emerging/multidisciplinary areas and Minor/Hons lists (11.4). Annexure-12 gives closest UG nomenclature for diploma courses (level conversion); Annexure-13 maps major disciplines to relevant branches. Parse these tables from `docs/reference/APH_2024-27.txt` into seed JSON.
- **Regions and competent authorities (Annexure-14):** AICTE regions (Central, Eastern, Northern, North Western, South Central, Southern, South Western, Western) with state-wise competent authorities for site plan, building plan, land-use certificate and occupancy certificate. Use for region assignment and the document checklist (for example Uttar Pradesh and Delhi rows).
- **Committee compositions (Annexure-16)** and role descriptions (16.8).
- **Mandatory-disclosure field list (Annexure-18).**
- **Accreditation criteria thresholds:** NAAC 3.01 (4-point), NBA 30%/50% courses, NBA 650 and 700 (of 1000), NIRF top 200, QS Asia 2024, autonomy, >80% admissions for 5 years.

---

## 11. Features the handbook implies that the earlier plan did not have
1. Self-disclosure **Deficiency Report** generator (portal feature, 2.3.3b).
2. **Fee calculator** and refund engine from the TER tables, including late penalty and additional-committee fees.
3. **Extended-EoA eligibility checker** (six criteria) and off-campus/FN/OCI/working-professional/TFW eligibility checkers.
4. **Intake and seat calculator** (approved intake, NRI 5%, FN/OCI 15%, lateral 10%, TFW 5%, EWS) and **faculty requirement calculator** (S/ratio × cadre 1:2:6, 25% reduction, adjunct caps).
5. **Built-up area / library / PC / bandwidth calculators** from approved intake.
6. **Complaint management** (PGRC → SCSC → show-cause → SHC → EC) and **penal-action** tracker with hearing before action.
7. **Security Deposit lifecycle:** creation, 15-day clock, 10%/20% penalties, release procedure with clearances, forfeiture, 10%/50% penalties on closure.
8. **Closure, hibernation, break-in-EoA, restoration** flows with their time limits.
9. **Mandatory-disclosure compliance checker** (Annexure-18 fields, website URL, single-PDF rule).
10. **Committee constitution engine** with automated random selection, conflict rules and compositions.
11. **Affidavit/document generator** for common affidavit shells and the Format 1-3 resolution templates (as downloadable PDFs, fictional data).
12. Institution **status tracker with unique application number** (1.4.1d) and **approved intake ledger** per academic year.

---

## 12. Ambiguities and inconsistencies in the PDF (flag, do not guess)
1. **Core-branch reduction:** 2.6g allows reduction up to 50% of approved intake (not below 30); 2.18a says reduction of core branches up to 30 seats.
2. **Appeal clock:** 1.11a counts 7 days from issue of the LoD; 2.24a counts 7 days from uploading of the decision. Make the start event configurable per track.
3. **Cross-references to missing clauses:** Annexure-2.1(iii) cites "Clause 7.17" for occupancy certificates (the occupancy rule is in 6.17g); Annexure-3 3.2f cites "Chapter VII" for barrier-free/sports (these appear in 6.52, 6.31); 2.18b cites Annexure 6/7 for nomenclature (nomenclature is Annexure-11); 2.13.1/Annexure-2.4 cites "Clause 2.10.2(b)" which does not exist in this handbook.
4. **Security Deposit term:** text says 10 years; Affidavit 6 says "8 years/10 years".
5. **Table 1.3** divisions column for E&T shows "6/12"; interpret as 6 (60-seat) or 12 (30-seat) divisions and keep it configurable.
6. **Dates are examples tied to AY 2024-25** (NBA validity till 30 Apr 2025, NIRF 8th edition, QS Asia 2024, previous LoR year AY 2023-24). Store them as editable "reference year" parameters.
7. **Course lists** contain duplicates and spelling variants (e.g. "Chemical Engineering (Petrochemical)" twice); normalise during seeding.
8. Table 2.3 shows "–" under Self-Disclosure for types that other clauses require to have "Nil Deficiency based on Self-Disclosure".
10. **PG cadre ratio:** footnotes give R = 3 for PG E&T and HMCT and R = 9 for MCA/MBA/PGDM; PG Planning, Applied Arts and Design are unmarked. Keep R configurable per programme/level.
9. Scrutiny for Chapter I is described as presenting originals; online mode is the norm and recordings are made "for transparency".

---

## 13. Out of scope (present in the PDF, not needed for the software)
Curriculum guidance (credits, Hons/Minor 18–20 credits, 160 credits base), the Sanskrit/IKS verses on page footers, detailed nomenclature lists beyond seeding, scholarship schemes, admission test weightages for PGDM (kept only as a rule note), student induction and UHV details, and the portal's own screen layouts.
