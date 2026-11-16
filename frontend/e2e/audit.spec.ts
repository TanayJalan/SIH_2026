import path from "node:path";
import { fileURLToPath } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { API_URL, PASSWORD, signIn, tokenFor } from "./helpers";

/**
 * Role and route audit.
 *
 * For every demo role this walks every route in the application at desktop and
 * mobile widths, writes a screenshot to docs/screens, runs axe, and records
 * console errors. Serious or critical axe findings fail the test; moderate and
 * minor findings are printed so they can be triaged.
 *
 * Run with: npm run test:e2e -- audit.spec.ts
 */

const SCREENS_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../docs/screens",
);
const VIEWPORTS = [
  { name: "1440", width: 1440, height: 900 },
  { name: "390", width: 390, height: 844 },
] as const;

interface RoleAccount {
  key: string;
  email: string;
}

const ROLES: RoleAccount[] = [
  { key: "institution-admin", email: "institution@example.edu" },
  { key: "regulation-bureau", email: "regulation@example.edu" },
  { key: "scrutiny-member", email: "scrutiny@example.edu" },
  { key: "evc-member", email: "inspection@example.edu" },
  { key: "regional-officer", email: "regional@example.edu" },
  { key: "shc-member", email: "shc@example.edu" },
  { key: "sac-member", email: "sac@example.edu" },
  { key: "executive-committee", email: "ec@example.edu" },
  { key: "complaint-scrutiny", email: "complaints@example.edu" },
  { key: "super-admin", email: "admin@example.edu" },
];

interface RouteTarget {
  name: string;
  path: string;
}

interface ApplicationItem {
  id: string;
  status: string;
}

async function applicationRoutes(
  request: Parameters<typeof tokenFor>[0],
  email: string,
): Promise<RouteTarget[]> {
  const token = await tokenFor(request, email);
  const response = await request.get(`${API_URL}/applications?page_size=100`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    return [];
  }
  const items = ((await response.json()) as { items: ApplicationItem[] }).items;
  const routes: RouteTarget[] = [];

  const detail = items.find((item) => item.status !== "DRAFT") ?? items[0];
  if (detail) {
    routes.push({ name: "application-detail", path: `/applications/${detail.id}` });
  }

  const draft = items.find((item) => item.status === "DRAFT");
  if (draft && email.startsWith("institution")) {
    routes.push({ name: "application-wizard", path: `/applications/${draft.id}/edit` });
  }

  return routes;
}

const STATIC_ROUTES: RouteTarget[] = [
  { name: "overview", path: "/" },
  { name: "dashboard", path: "/dashboard" },
  { name: "applications", path: "/applications" },
  { name: "application-new", path: "/applications/new" },
  { name: "eligibility", path: "/eligibility" },
  { name: "compliance", path: "/compliance" },
  { name: "alerts", path: "/alerts" },
  { name: "alert-rules", path: "/alert-rules" },
  { name: "audit-logs", path: "/audit-logs" },
  { name: "profile", path: "/profile" },
  { name: "design-system", path: "/dev/ui" },
  { name: "not-found", path: "/this-route-does-not-exist" },
];

const IGNORED_CONSOLE = [
  /ResizeObserver loop/i,
  /Download the React DevTools/i,
  /\[vite\]/i,
];

function collectConsole(page: Page): string[] {
  const messages: string[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error" && message.type() !== "warning") {
      return;
    }
    const text = message.text();
    if (IGNORED_CONSOLE.some((pattern) => pattern.test(text))) {
      return;
    }
    messages.push(`${message.type()}: ${text}`);
  });
  page.on("pageerror", (error) => {
    messages.push(`pageerror: ${error.message}`);
  });
  return messages;
}

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("domcontentloaded");
  await page.locator("h1").first().waitFor({ state: "visible", timeout: 20_000 });
  /* Give charts, the map and count-up numbers a frame or two to paint. */
  await page.waitForTimeout(500);
}

test.describe("role and route audit", () => {
  test.use({ reducedMotion: "reduce" });

  for (const role of ROLES) {
    test(`${role.key} screens, axe and console`, async ({ page, request }) => {
      test.setTimeout(600_000);

      const routes = [...STATIC_ROUTES, ...(await applicationRoutes(request, role.email))];
      const consoleMessages = collectConsole(page);
      const findings: string[] = [];

      await signIn(page, role.email);

      for (const viewport of VIEWPORTS) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        for (const route of routes) {
          await test.step(`${route.name} @ ${viewport.name}`, async () => {
            await page.goto(route.path);
            await settle(page);

            const screenshotPath = path.join(
              SCREENS_ROOT,
              role.key,
              viewport.name,
              `${route.name}.png`,
            );
            await page.screenshot({
              path: screenshotPath,
              animations: "disabled",
              /*
               * A stalled compositor frame should fail this step quickly
               * instead of consuming the whole per-role test timeout.
               */
              timeout: 30_000,
            });

            const results = await new AxeBuilder({ page }).analyze();
            const blocking = results.violations.filter(
              (violation) => violation.impact === "serious" || violation.impact === "critical",
            );
            const advisory = results.violations.filter(
              (violation) => violation.impact !== "serious" && violation.impact !== "critical",
            );

            if (advisory.length > 0) {
              console.log(
                `[axe:${role.key}:${viewport.name}:${route.name}] ` +
                  advisory
                    .map((violation) => `${violation.id} (${violation.impact})`)
                    .join(", "),
              );
            }

            for (const violation of blocking) {
              findings.push(
                `${viewport.name} ${route.name}: ${violation.id} [${violation.impact}] ` +
                  `${violation.help} :: ${violation.nodes
                    .map((node) => node.target.join(" "))
                    .slice(0, 6)
                    .join(" | ")}`,
              );
            }
          });
        }
      }

      expect(findings, "serious or critical axe findings").toEqual([]);
      expect(consoleMessages, "console errors or warnings").toEqual([]);
    });
  }
});
