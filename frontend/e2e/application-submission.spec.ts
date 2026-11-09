import { expect, test } from "@playwright/test";

import { INSTITUTION, completeDraft, signIn } from "./helpers";

/**
 * Institution submission smoke test.
 *
 * The draft is completed through the API (profile, faculty, finance,
 * accreditation, mandatory documents and the TER payment) so the browser flow
 * only exercises the final Review step and the submit endpoint.
 */
test("submits a completed draft", async ({ page, request }) => {
  const applicationId = await completeDraft(request);

  await signIn(page, INSTITUTION);
  await page.goto(`/applications/${applicationId}/edit`);

  const reviewStep = page.getByRole("button", { name: "Review", exact: true });
  await expect(reviewStep).toBeVisible();
  await reviewStep.click();
  await expect(page.getByRole("heading", { name: "Review" })).toBeVisible();

  const submit = page.getByRole("button", { name: "Submit application" });
  await expect(submit).toBeEnabled();
  await submit.click();

  await expect(
    page.getByRole("heading", { name: "Application submitted" }),
  ).toBeVisible({ timeout: 30_000 });
});
