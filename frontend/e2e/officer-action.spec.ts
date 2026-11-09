import { expect, test } from "@playwright/test";

import { SCRUTINY, findAssignedScrutinyCase, signIn } from "./helpers";

/**
 * Scrutiny officer action smoke test.
 *
 * The seeded case AICTE/2026-27/0000109 is in Scrutiny, assigned to the demo
 * scrutiny officer and free of open deficiencies, so the "Recommend an Expert
 * Visit Committee" edge is available. The state machine moves the case to
 * EVC_CONSTITUTED and the case header re-renders the status.
 */
test("scrutiny recommends an Expert Visit Committee", async ({ page, request }) => {
  const applicationId = await findAssignedScrutinyCase(
    request,
    "AICTE/2026-27/0000109",
  );

  await signIn(page, SCRUTINY);
  await page.goto(`/applications/${applicationId}`);

  const trigger = page.getByRole("button", {
    name: "Recommend an Expert Visit Committee",
  });
  await expect(trigger).toBeVisible();
  await trigger.click();

  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Recommend an Expert Visit Committee" }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Recommend an Expert Visit Committee" })
    .click();

  await expect(page.getByText("Evc constituted").first()).toBeVisible({
    timeout: 30_000,
  });
});
