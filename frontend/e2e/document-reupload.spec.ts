import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Acceptance flow for the document re-upload cycle.
 *
 * A Scrutiny Committee member rejects the fire-safety certificate with the
 * EXPIRED reason, the institution sees the reason and re-uploads version 2, the
 * linked deficiency is marked responded, and the reviewer verifies the
 * replacement (APH 1.8f, 1.8g, 2.4).
 *
 * The case is created through the API so the test is deterministic and does not
 * depend on which seeded application happens to be in Scrutiny.
 */

const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
const PASSWORD = process.env.E2E_PASSWORD ?? "ChangeMe123!";

const INSTITUTION = "institution@example.edu";
const SCRUTINY = "scrutiny@example.edu";
const REGULATION = "regulation@example.edu";

const COMPLETE_APPLICATION_DATA = {
  institution_profile: {
    head_name: "Dr Demo Registrar",
    address_line1: "1 Fictional Campus Road",
    address_line2: "Demo Nagar",
    city: "Pune",
    state: "Maharashtra",
    pin_code: "411001",
    contact_email: "registrar@example.edu",
    contact_phone: "+91 98765 43210",
    website: "https://example.edu",
  },
  infrastructure: {
    land_area: 12000,
    built_up_area: 8500,
    labs: 18,
    library: 24000,
    hostel: 300,
  },
  faculty: {
    total: 120,
    professors: 15,
    associate_professors: 35,
    assistant_professors: 70,
    student_faculty_ratio: 18.5,
    phd_faculty_ratio: 42,
  },
  finance: {
    tuition_fee: 150000,
    development_fee: 25000,
    other_fees: 10000,
    balance: 1250000,
  },
  accreditation: {
    naac_grade: "A",
    nba_status: "ACCREDITED",
    last_validated_on: "2025-06-30",
  },
  mandatory_disclosure_url: "https://example.edu/mandatory-disclosure",
};

function pdfFor(docType: string): Buffer {
  return Buffer.from(
    `%PDF-1.4\n${docType.replaceAll("_", " ")} fictional demo document\n`,
    "utf8",
  );
}

async function tokenFor(request: APIRequestContext, email: string): Promise<string> {
  const response = await request.post(`${API_URL}/auth/login`, {
    data: { email, password: PASSWORD },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as { access_token: string };
  return body.access_token;
}

/** Create, complete, pay and submit a case, then hand it to the scrutiny member. */
async function createCaseInScrutiny(request: APIRequestContext): Promise<string> {
  const institution = await tokenFor(request, INSTITUTION);
  const institutionHeaders = { Authorization: `Bearer ${institution}` };

  const created = await request.post(`${API_URL}/applications`, {
    headers: institutionHeaders,
    data: { application_type: "NEW_INSTITUTION", academic_year: "2026-27" },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const applicationId = ((await created.json()) as { id: string }).id;

  const updated = await request.patch(`${API_URL}/applications/${applicationId}`, {
    headers: institutionHeaders,
    data: { data: COMPLETE_APPLICATION_DATA },
  });
  expect(updated.ok(), await updated.text()).toBeTruthy();

  const checklist = await request.get(
    `${API_URL}/applications/${applicationId}/documents/checklist`,
    { headers: institutionHeaders },
  );
  expect(checklist.ok(), await checklist.text()).toBeTruthy();
  const documents = (
    (await checklist.json()) as {
      documents: { doc_type: string; mandatory: boolean }[];
    }
  ).documents;
  for (const document of documents) {
    if (!document.mandatory) {
      continue;
    }
    const uploaded = await request.post(
      `${API_URL}/applications/${applicationId}/documents`,
      {
        headers: institutionHeaders,
        multipart: {
          doc_type: document.doc_type,
          signed_with_dsc: "true",
          file: {
            name: `${document.doc_type.toLowerCase()}.pdf`,
            mimeType: "application/pdf",
            buffer: pdfFor(document.doc_type),
          },
        },
      },
    );
    expect(uploaded.status(), await uploaded.text()).toBe(201);
  }

  const paid = await request.post(`${API_URL}/applications/${applicationId}/fee/pay`, {
    headers: institutionHeaders,
    data: { payment_method: "SIMULATED", confirm: true },
  });
  expect(paid.ok(), await paid.text()).toBeTruthy();

  const submitted = await request.post(`${API_URL}/applications/${applicationId}/submit`, {
    headers: institutionHeaders,
  });
  expect(submitted.ok(), await submitted.text()).toBeTruthy();

  const regulation = await tokenFor(request, REGULATION);
  const assigned = await request.post(
    `${API_URL}/applications/${applicationId}/actions/assign_scrutiny`,
    { headers: { Authorization: `Bearer ${regulation}` } },
  );
  expect(assigned.ok(), await assigned.text()).toBeTruthy();

  return applicationId;
}

async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function openDocuments(page: Page, applicationId: string): Promise<void> {
  await page.goto(`/applications/${applicationId}`);
  await page.getByRole("tab", { name: "Documents" }).click();
}

test("rejected fire certificate is re-uploaded and verified", async ({ page, request }) => {
  const applicationId = await createCaseInScrutiny(request);

  // 1. The Scrutiny Committee member rejects the expired fire certificate.
  await signIn(page, SCRUTINY);
  await openDocuments(page, applicationId);

  const fireRow = page
    .locator("li")
    .filter({ hasText: "Fire Safety Certificate" })
    .first();
  await expect(fireRow).toBeVisible();
  await fireRow.getByRole("button", { name: "Reject" }).click();

  const rejectDialog = page.getByRole("dialog");
  await expect(rejectDialog.getByText("Reject Fire Safety Certificate")).toBeVisible();
  await rejectDialog.getByRole("combobox", { name: "Reason" }).click();
  await page.getByRole("option", { name: "Expired certificate" }).click();
  await rejectDialog
    .getByLabel("Comment for the institution")
    .fill("The fire certificate expired on 31 December 2025. Upload a current certificate.");
  await rejectDialog.getByRole("button", { name: "Reject document" }).click();

  await expect(page.getByText("Document rejected").first()).toBeVisible();
  await expect(fireRow.getByText("Rejected").first()).toBeVisible();
  await expect(fireRow.getByText("Expired certificate").first()).toBeVisible();

  // 2. The institution sees the reason and replaces exactly that document.
  await signIn(page, INSTITUTION);
  await openDocuments(page, applicationId);

  const rejectedRow = page
    .locator("li")
    .filter({ hasText: "Fire Safety Certificate" })
    .first();
  await expect(rejectedRow.getByText("The fire certificate expired").first()).toBeVisible();

  await rejectedRow.getByRole("button", { name: "Re-upload" }).click();
  const reuploadDialog = page.getByRole("dialog");
  await expect(
    reuploadDialog.getByText("Re-upload Fire Safety Certificate"),
  ).toBeVisible();
  await reuploadDialog.locator('input[type="file"]').setInputFiles({
    name: "fire-safety-certificate-2026.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from(
      "%PDF-1.4\nFire safety certificate renewed for the fictional institution\n",
      "utf8",
    ),
  });
  await reuploadDialog.getByRole("checkbox").check();
  await reuploadDialog.getByLabel("Signed by").fill("Dr Demo Registrar");
  await reuploadDialog.getByLabel(/Certificate valid until/).fill("2027-12-31");
  await reuploadDialog.getByRole("button", { name: /Re-upload as version 2/ }).click();

  await expect(page.getByText("Document re-uploaded (version 2)").first()).toBeVisible();
  const replacedRow = page
    .locator("li")
    .filter({ hasText: "Fire Safety Certificate" })
    .first();
  await expect(replacedRow.getByText("Resubmitted (v2)").first()).toBeVisible();
  await expect(replacedRow.getByText("Pending").first()).toBeVisible();

  // The deficiency item is answered by the replacement.
  await page.getByRole("tab", { name: "Deficiencies" }).click();
  await expect(page.getByText("Responded").first()).toBeVisible();

  // 3. Re-Scrutiny shows only the replacement and verifies it.
  await signIn(page, SCRUTINY);
  await openDocuments(page, applicationId);
  await page.getByRole("checkbox", { name: /Only documents to re-check/ }).check();

  const recheckRow = page
    .locator("li")
    .filter({ hasText: "Fire Safety Certificate" })
    .first();
  await expect(recheckRow.getByText("Resubmitted (v2)").first()).toBeVisible();
  await recheckRow.getByRole("button", { name: "Verify" }).click();
  // With the "only to re-check" filter on, the verified row leaves the list.
  await expect(
    page.getByText("No documents are waiting to be re-checked."),
  ).toBeVisible();
});
