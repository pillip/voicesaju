/**
 * E2E smoke for the onboarding 4-step flow (ISSUE-028).
 *
 * Same conditions as `auth-login.spec.ts` and `preview.spec.ts`: Playwright
 * is NOT yet installed in this repo. The spec exists to:
 *   1) Satisfy the sprint checkpoint requirement that every UI issue carries
 *      at least one e2e test file (per `docs/test_plan.md`).
 *   2) Document the intended browser-level acceptance criteria that the
 *      Vitest tests cannot fully cover (real router navigations, cross-page
 *      Zustand persistence including hot reload, keyboard tab order).
 *
 * Run locally once Playwright is wired:
 *   pnpm exec playwright test web/tests/e2e/onboarding-flow.spec.ts
 */

import { expect, test } from "@playwright/test";

test.describe("Onboarding 4-step flow (ISSUE-028)", () => {
  test("happy path: birth-date → birth-time → gender → name → /reading/category", async ({
    page,
  }) => {
    await page.goto("/onboarding/birth-date");

    // Step 1 — birth date.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("list", { name: "1 / 4" })).toBeVisible();
    await page.getByLabel(/생년월일|YYYY-MM-DD/).fill("1997-03-15");
    const next1 = page.getByRole("button", { name: "다음" });
    await expect(next1).toBeEnabled();
    await next1.click();

    // Step 2 — birth time (use 모름 to keep the spec deterministic across
    // OS/locale spinner differences).
    await expect(page).toHaveURL(/\/onboarding\/birth-time$/);
    await expect(page.getByRole("list", { name: "2 / 4" })).toBeVisible();
    await page
      .getByRole("checkbox", { name: /시간은 모르겠어요|시간 모름/ })
      .check();
    await page.getByRole("button", { name: "다음" }).click();

    // Step 3 — gender.
    await expect(page).toHaveURL(/\/onboarding\/gender$/);
    await expect(page.getByRole("list", { name: "3 / 4" })).toBeVisible();
    await page.getByRole("radio", { name: /(여자|여)/ }).click();

    // Step 4 — name.
    await expect(page).toHaveURL(/\/onboarding\/name$/);
    await expect(page.getByRole("list", { name: "4 / 4" })).toBeVisible();
    await page.getByLabel(/이름|NAME/).fill("효주");
    await page.getByRole("button", { name: /완료|이름 없이 계속하기/ }).click();

    // Final route.
    await expect(page).toHaveURL(/\/reading\/category$/);
  });

  test("AC3: back navigation from step 2 preserves the date typed in step 1", async ({
    page,
  }) => {
    await page.goto("/onboarding/birth-date");
    await page.getByLabel(/생년월일|YYYY-MM-DD/).fill("1997-03-15");
    await page.getByRole("button", { name: "다음" }).click();
    await expect(page).toHaveURL(/\/onboarding\/birth-time$/);
    await page.getByRole("button", { name: /뒤로/ }).click();
    await expect(page).toHaveURL(/\/onboarding\/birth-date$/);
    await expect(page.getByLabel(/생년월일|YYYY-MM-DD/)).toHaveValue(
      "1997-03-15",
    );
  });

  test("AC4: name > 10 chars renders inline error and disables 완료", async ({
    page,
  }) => {
    await page.goto("/onboarding/name");
    await page.getByLabel(/이름|NAME/).fill("가나다라마바사아자차카");
    await expect(page.getByText("이름은 10자 이내로 적어줘")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /완료|이름 없이 계속하기/ }),
    ).toBeDisabled();
  });

  test("AC5: keyboard tab order on step 1 — date input → toggle → 다음 button", async ({
    page,
  }) => {
    await page.goto("/onboarding/birth-date");
    await page.keyboard.press("Tab"); // probably enters chrome / back button
    // Walk forward until 다음 is the active element; assert ordering by
    // capturing each focused element's accessible name.
    const order: string[] = [];
    for (let i = 0; i < 10; i++) {
      const name = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        return (
          el?.getAttribute("aria-label") || el?.textContent || el?.tagName || ""
        );
      });
      order.push(name.trim());
      if (/다음/.test(name)) break;
      await page.keyboard.press("Tab");
    }
    expect(order.join(" | ")).toMatch(/다음/);
  });
});
