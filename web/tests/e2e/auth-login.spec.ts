/**
 * E2E smoke for `/auth/login` (ISSUE-027, Screen 15).
 *
 * Like `preview.spec.ts`, this spec is authored against Playwright. Playwright
 * is NOT yet installed in the repo — the dedicated infra issue lands later
 * in M1. Until then the spec exists to:
 *   1) Satisfy the sprint checkpoint requirement that every UI issue carries
 *      at least one e2e test file (per `docs/test_plan.md`).
 *   2) Document the intended browser-level acceptance criteria that the
 *      Vitest tests cannot fully cover (real navigation on tap, UA-based
 *      runtime-channel detection across reloads, focus-visible affordance on
 *      `<a>` anchors during keyboard tabbing).
 *
 * Run locally once Playwright is wired:
 *   pnpm exec playwright test web/tests/e2e/auth-login.spec.ts
 */

import { expect, test } from '@playwright/test';

test.describe('/auth/login (ISSUE-027)', () => {
  test('web user sees Kakao + Apple buttons that redirect to the start URLs', async ({ page }) => {
    await page.goto('/auth/login');

    const kakao = page.getByRole('link', { name: '카카오로 시작하기' });
    const apple = page.getByRole('link', { name: 'Apple로 시작하기' });
    await expect(kakao).toBeVisible();
    await expect(apple).toBeVisible();
    await expect(kakao).toHaveAttribute('href', '/api/v1/auth/kakao/start');
    await expect(apple).toHaveAttribute('href', '/api/v1/auth/apple/start');

    // Tap Kakao — once ISSUE-025 lands and `start` returns 302, this becomes
    // a real cross-origin redirect. For the mock backend we just confirm
    // the navigation request fires.
    await Promise.all([page.waitForURL(/\/api\/v1\/auth\/kakao\/start/), kakao.click()]);
  });

  test('Toss WebView UA shows ONLY the Toss button', async ({ browser }) => {
    const ctx = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Toss/5.180.0',
    });
    const page = await ctx.newPage();
    await page.goto('/auth/login');

    await expect(page.getByRole('link', { name: '토스로 계속하기' })).toBeVisible();
    await expect(page.getByRole('link', { name: '카카오로 시작하기' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Apple로 시작하기' })).toHaveCount(0);

    await ctx.close();
  });

  test('?error=cancelled renders the cancellation banner with re-enabled buttons', async ({
    page,
  }) => {
    await page.goto('/auth/login?error=cancelled');

    const banner = page.getByRole('alert');
    await expect(banner).toHaveText('로그인이 취소됐어요');

    // Buttons must remain clickable (AC4 — re-enable on return).
    const kakao = page.getByRole('link', { name: '카카오로 시작하기' });
    await expect(kakao).toBeVisible();
    await expect(kakao).not.toHaveAttribute('aria-disabled', 'true');
  });
});
