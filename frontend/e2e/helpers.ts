import { expect, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Shared helpers for the Playwright smoke tests.
 *
 * Cases are created through the API so a test never depends on which seeded
 * application happens to be in a given state; the browser is then used for the
 * action under test.
 */

export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";
export const PASSWORD = process.env.E2E_PASSWORD ?? "ChangeMe123!";

export const INSTITUTION = "institution@example.edu";
export const SCRUTINY = "scrutiny@example.edu";
export const REGULATION = "regulation@example.edu";
export const SUPER_ADMIN = "admin@example.edu";

export const COMPLETE_APPLICATION_DATA = {
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

export function pdfFor(label: string): Buffer {
  return Buffer.from(`%PDF-1.4\n${label} fictional demo document\n`, "utf8");
}

export async function tokenFor(
  request: APIRequestContext,
  email: string,
): Promise<string> {
  const response = await request.post(`${API_URL}/auth/login`, {
    data: { email, password: PASSWORD },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as { access_token: string };
  return body.access_token;
}

export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

export async function createDraft(
  request: APIRequestContext,
  headers: Record<string, string>,
): Promise<string> {
  const created = await request.post(`${API_URL}/applications`, {
    headers,
    data: { application_type: "NEW_INSTITUTION", academic_year: "2026-27" },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  return ((await created.json()) as { id: string }).id;
}

async function mandatoryDocuments(
  request: APIRequestContext,
  headers: Record<string, string>,
  applicationId: string,
): Promise<{ doc_type: string; mandatory: boolean }[]> {
  const checklist = await request.get(
    `${API_URL}/applications/${applicationId}/documents/checklist`,
    { headers },
  );
  expect(checklist.ok(), await checklist.text()).toBeTruthy();
  return (
    (await checklist.json()) as {
      documents: { doc_type: string; mandatory: boolean }[];
    }
  ).documents;
}

async function uploadPdf(
  request: APIRequestContext,
  headers: Record<string, string>,
  applicationId: string,
  docType: string,
  options: { validUntil?: string } = {},
): Promise<void> {
  const { validUntil } = options;
  const uploaded = await request.post(
    `${API_URL}/applications/${applicationId}/documents`,
    {
      headers,
      multipart: {
        doc_type: docType,
        signed_with_dsc: "true",
        ...(validUntil ? { valid_until: validUntil } : {}),
        file: {
          name: `${docType.toLowerCase()}.pdf`,
          mimeType: "application/pdf",
          buffer: pdfFor(docType),
        },
      },
    },
  );
  expect(uploaded.status(), await uploaded.text()).toBe(201);
}

/** Create, complete, upload and pay a draft, leaving only the submit click. */
export async function completeDraft(
  request: APIRequestContext,
): Promise<string> {
  const token = await tokenFor(request, INSTITUTION);
  const headers = { Authorization: `Bearer ${token}` };
  const applicationId = await createDraft(request, headers);

  const updated = await request.patch(`${API_URL}/applications/${applicationId}`, {
    headers,
    data: { data: COMPLETE_APPLICATION_DATA },
  });
  expect(updated.ok(), await updated.text()).toBeTruthy();

  for (const document of await mandatoryDocuments(request, headers, applicationId)) {
    if (document.mandatory) {
      await uploadPdf(request, headers, applicationId, document.doc_type);
    }
  }

  const paid = await request.post(`${API_URL}/applications/${applicationId}/fee/pay`, {
    headers,
    data: { payment_method: "SIMULATED", confirm: true },
  });
  expect(paid.ok(), await paid.text()).toBeTruthy();
  return applicationId;
}

/**
 * Find a seeded case in Scrutiny that is already assigned to the demo scrutiny
 * officer.
 *
 * The demo seed gives institution admins their city as ``region`` while
 * scrutiny officers carry the AICTE region, so a freshly submitted case cannot
 * be auto-assigned in this dataset. The pre-staged case is the same one the
 * demo script uses; run ``make reset-demo`` to restore it after a run.
 */
export async function findAssignedScrutinyCase(
  request: APIRequestContext,
  portalApplicationNo: string,
): Promise<string> {
  const token = await tokenFor(request, SCRUTINY);
  const response = await request.get(
    `${API_URL}/applications?assigned_to_me=true&page_size=100`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(response.ok(), await response.text()).toBeTruthy();
  const page = (await response.json()) as {
    items: { id: string; portal_application_no: string | null; status: string }[];
  };
  const match = page.items.find(
    (item) =>
      item.portal_application_no === portalApplicationNo && item.status === "SCRUTINY",
  );
  expect(
    match,
    `no SCRUTINY case ${portalApplicationNo} is assigned to ${SCRUTINY}`,
  ).toBeTruthy();
  return match!.id;
}

/** Reset the DEBUG-only demo clock to real time before a time-dependent test. */
export async function resetDemoClock(request: APIRequestContext): Promise<void> {
  const token = await tokenFor(request, INSTITUTION);
  const response = await request.post(`${API_URL}/dev/simulate-time`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { reset: true },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

/** Advance the demo clock by whole days and run the alert scan. */
export async function advanceDemoClock(
  request: APIRequestContext,
  days: number,
): Promise<void> {
  const token = await tokenFor(request, INSTITUTION);
  const response = await request.post(`${API_URL}/dev/simulate-time`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { days },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

/**
 * Create a draft with one mandatory document that expires in three days.
 *
 * A fresh document id makes the alert dedupe key unique, so the live-update
 * test can run repeatedly against the same database.
 */
export async function createExpiringDocumentCase(
  request: APIRequestContext,
): Promise<{ applicationId: string; docType: string }> {
  const token = await tokenFor(request, INSTITUTION);
  const headers = { Authorization: `Bearer ${token}` };
  const applicationId = await createDraft(request, headers);

  const documents = await mandatoryDocuments(request, headers, applicationId);
  const mandatory = documents.find((document) => document.mandatory);
  expect(mandatory, "the seeded checklist has no mandatory document").toBeTruthy();

  const expiry = new Date();
  expiry.setDate(expiry.getDate() + 3);
  const validUntil = expiry.toISOString().slice(0, 10);
  await uploadPdf(
    request,
    headers,
    applicationId,
    mandatory!.doc_type,
    { validUntil },
  );
  return { applicationId, docType: mandatory!.doc_type };
}
