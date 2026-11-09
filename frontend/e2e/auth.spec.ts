import { expect, test } from "@playwright/test";

import { INSTITUTION, PASSWORD } from "./helpers";

/**
 * Sign-in smoke test.
 *
 * The happy path uses a seeded demo account and lands on the role-specific
 * workspace. The failure path proves a wrong password stays on the form and
 * surfaces the API error without leaking which field was wrong.
 */
test.describe("authentication", () => {
  test("signs in with a seeded demo account", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email address").fill(INSTITUTION);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).not.toHaveURL(/\/login/);
    await expect(
      page.getByRole("link", { name: "My applications", exact: true }),
    ).toBeVisible();
  });

  test("rejects an invalid password", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email address").fill(INSTITUTION);
    await page.getByLabel("Password", { exact: true }).fill("not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Invalid email or password")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });
});
