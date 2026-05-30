/**
 * E2E smoke for /reading/category (ISSUE-030).
 *
 * Same convention as `auth-login.spec.ts` and `onboarding-flow.spec.ts`:
 * Playwright is NOT yet wired in this repo. The spec exists to:
 *   1) Satisfy the checkpoint that every UI issue carries an e2e file
 *      (per docs/test_plan.md).
 *   2) Document the AC2 navigation intent at the browser level — Vitest can
 *      assert router.push, but only a real browser confirms the URL changes
 *      and that the destination route doesn't crash (the destination is
 *      ISSUE-032; until then this spec stays skipped).
 *
 * Run locally once Playwright is wired:
 *   pnpm exec playwright test web/tests/e2e/category-screen.spec.ts
 */

import { expect, test } from '@playwright/test';

test.describe('/reading/category (ISSUE-030)', () => {
  test('AC2: tap a category card → navigate to /reading/intro/[category]', async ({ page }) => {
    await page.goto('/reading/category');
    // Greeting visible — uses the "거기 너" anonymous addressee for a fresh
    // session with no stored name.
    await expect(page.getByTestId('greeting')).toContainText('거기 너');
    // Tap the love card; expect URL transition. The destination renders 404
    // until ISSUE-032 ships its page; what we assert here is the URL change.
    await page.getByTestId('category-card-love').click();
    await expect(page).toHaveURL(/\/reading\/intro\/love$/);
  });

  test('AC3: subscriber state surfaces the sticky bottom bar', async ({ page }) => {
    // Dev-only override for the entitlement stub until ISSUE-040 lands.
    await page.goto('/reading/category?entitlement=subscription');
    await expect(page.getByTestId('subscriber-bottom-bar')).toContainText('구독 중 — 이번 달 사주');
  });
});
