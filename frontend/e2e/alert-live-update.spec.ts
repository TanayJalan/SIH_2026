import { expect, test } from "@playwright/test";

import {
  INSTITUTION,
  advanceDemoClock,
  createExpiringDocumentCase,
  resetDemoClock,
  signIn,
} from "./helpers";

/**
 * Live alert smoke test.
 *
 * The test resets the DEBUG-only demo clock, creates a fresh draft with a
 * document that expires in three days, opens the alert inbox (which subscribes
 * to the SSE stream), then advances the clock by one day. The scan raises a
 * DOCUMENT_EXPIRING alert for the institution admin, and the streamed event
 * appears as a toast without a page reload.
 */
test("an expiring document raises a live alert", async ({ page, request }) => {
  await resetDemoClock(request);
  await createExpiringDocumentCase(request);

  await signIn(page, INSTITUTION);

  const streamReady = page.waitForResponse(
    (response) =>
      response.url().includes("/alerts/stream") && response.status() === 200,
  );
  await page.goto("/alerts");
  await streamReady;

  await advanceDemoClock(request, 1);

  await expect(page.getByText(/^Document expiring:/).first()).toBeVisible({
    timeout: 30_000,
  });
});
