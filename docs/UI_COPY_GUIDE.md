# UI copy guide

Voice: calm, specific and procedural. The interface supports an official approval process, so every sentence should help an officer or institution take the next step.

## Rules

### 1. Use sentence case

Capitalise the first word and proper nouns only. Do not use title case or all caps.

- Do: `Raise a deficiency`
- Do: `Send to committee`
- Don't: `Raise A Deficiency`
- Don't: `SEND TO COMMITTEE`

### 2. Lead with an active verb

Buttons, menu items and links name the action they perform. Avoid vague labels such as `Submit`, `Continue` or `OK` when a specific verb is available.

- Do: `Upload land record`
- Do: `Schedule inspection`
- Do: `Withdraw application`
- Don't: `Proceed`
- Don't: `Click here`

### 3. The success toast reuses the action verb

A success message confirms the same action the user just took. Keep the verb and the object.

| Action taken | Success toast |
| --- | --- |
| `Raise deficiency` | `Deficiency raised` |
| `Send to committee` | `Application sent to committee` |
| `Schedule inspection` | `Inspection scheduled` |
| `Upload land record` | `Land record uploaded` |

Add one line of consequence when it helps:

> **Deficiency raised**
> The institution can now respond with the requested document.

Do not say `Success!`, `Done` or `Saved successfully`. Those messages do not tell the user what changed.

### 4. Errors say what went wrong and how to fix it

An error needs three things:

1. What failed.
2. Why it failed, if known.
3. The next action.

- Do: `Enter a complete email address, such as registrar@institute.example.`
- Do: `Choose an inspection date on or after 29 October 2026.`
- Do: `Add a contact email for the institution, then try again.`
- Don't: `Invalid input`
- Don't: `Something went wrong`
- Don't: `Error 422`

If the cause is genuinely unknown, say what the user can do next: `The document could not be uploaded. Check the file size and try again.`

### 5. Empty states invite one action

Empty states use one line of explanation and one action. No decorative illustration, no second paragraph, no competing links.

- Do: `No inspections are scheduled this week.` with `Schedule inspection`
- Do: `No deficiency responses yet.` with `Send reminder`
- Don't: `Nothing to see here.`
- Don't: `No data.`

### 6. Labels describe the field, hints describe the help

Use a noun or noun phrase for labels. Put format and context in a hint.

- Label: `AICTE institution ID`
- Hint: `Use the ID shown on the latest approval letter.`
- Label: `Inspection date`
- Hint: `Choose a date at least seven days from today.`

Do not use the label to repeat the hint, and do not use placeholder text as the only label.

### 7. Dates, numbers and statuses

- Write dates as `22 October 2026` in prose. Use the native date format in date fields.
- Use `days left`, not `days remaining`.
- Use numerals for counts, scores and durations: `5 days`, `72%`, `24 applications`.
- Use tabular numerals for all numeric UI so values align.
- Status labels are: `Compliant`, `Watch`, `Breach`, `In progress`, `Not started`.
- Risk labels are: `Low risk`, `Medium risk`, `High risk`.

### 8. Keep terminology consistent

| Use | Avoid |
| --- | --- |
| institution | college, university (unless quoting a legal name) |
| application | request, submission |
| scrutiny | review (when referring to the scrutiny stage) |
| inspection committee | visiting team |
| deficiency | issue, problem |
| regional head | regional officer |
| approval letter | sanction letter |

The full flow is `Submitted > Documents > Scrutiny > Inspection > Committee > Decision`.

### 9. Do not use placeholder copy

Every word in the prototype must be real, meaningful interface copy. Do not ship lorem ipsum, `TBD`, `Coming soon`, `Sample text` or empty labels. When data is unknown, say what is known and what the user can do next.

### 10. Keep the tone procedural, not chatty

- Do: `The institution can respond until 29 October 2026.`
- Don't: `Hang tight while we work our magic.`
- Do: `This action cannot be undone.`
- Don't: `Are you sure?`

## Copy examples by component

| Component | Good copy | Avoid |
| --- | --- | --- |
| Primary button | `Raise deficiency` | `Submit` |
| Destructive button | `Withdraw application` | `Delete` |
| Dialog title | `Raise a deficiency` | `Confirm action` |
| Dialog body | `Tell the institution which document is missing and what to correct before scrutiny resumes.` | `Enter details here.` |
| Toast title | `Deficiency raised` | `Success` |
| Toast body | `The institution can now respond with the requested document.` | `Operation completed.` |
| Empty state | `No inspections are scheduled this week.` | `No data found.` |
| Field error | `Enter a complete email address, such as registrar@sunrise.example.` | `Invalid email.` |
| Tooltip | `The SLA is the working-day limit for the current approval stage.` | `Info` |

## Review checklist

- Is the label in sentence case?
- Does every button start with a verb and name the exact action?
- Does the success toast reuse that verb?
- Does every error name the problem and the fix?
- Does the empty state have one action?
- Are dates, numbers and statuses written consistently?
- Is every sentence real product copy rather than a placeholder?
