/**
 * E2E smoke for the /preview design-system page (ISSUE-021).
 *
 * This spec is authored against Playwright. Playwright is NOT yet installed in
 * the repo — the dedicated infra issue lands later in M1. Until then the spec
 * exists to:
 *   1) Satisfy the sprint checkpoint requirement that every UI issue carries
 *      at least one e2e test file (per `docs/test_plan.md`).
 *   2) Document the intended browser-level acceptance criteria that the
 *      vitest snapshots + axe-core unit test cannot fully cover (focus rings
 *      visible during real keyboard tabbing, computed Tailwind hex values
 *      applied to category tokens, full WCAG color-contrast at AA).
 *
 * Run locally once Playwright is wired:
 *   pnpm exec playwright test web/tests/e2e/preview.spec.ts
 */

import { expect, test } from '@playwright/test';

test.describe('Design system preview (ISSUE-021)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/preview');
  });

  test('renders all 8 base components in default + disabled + loading states', async ({ page }) => {
    const components = [
      'PrimaryButton',
      'SecondaryButton',
      'TertiaryLink',
      'CategoryCard',
      'OptionCard',
      'StepIndicator',
      'Toast',
      'Banner',
    ];
    for (const name of components) {
      await expect(page.getByTestId(`preview-${name}-default`)).toBeVisible();
      await expect(page.getByTestId(`preview-${name}-disabled`)).toBeVisible();
      await expect(page.getByTestId(`preview-${name}-loading`)).toBeVisible();
    }
  });

  test('category tokens resolve to the documented hex values', async ({ page }) => {
    const expected: Record<string, string> = {
      love: 'rgb(155, 74, 74)', // #9B4A4A
      work: 'rgb(61, 82, 102)', // #3D5266
      money: 'rgb(166, 124, 40)', // #A67C28
      tarot: 'rgb(91, 58, 92)', // #5B3A5C
    };
    for (const [key, rgb] of Object.entries(expected)) {
      const card = page.getByTestId(`category-card-${key}`);
      const bg = await card.evaluate((el) => window.getComputedStyle(el).backgroundColor);
      expect(bg).toBe(rgb);
    }
  });

  test('keyboard tab navigation surfaces a visible focus ring on every interactive element', async ({
    page,
  }) => {
    const interactive = await page
      .locator('button:not([disabled]), a, [role="radio"]:not([aria-disabled="true"])')
      .count();
    for (let i = 0; i < interactive; i++) {
      await page.keyboard.press('Tab');
      const active = page.locator(':focus');
      // Focus outline must be visible (non-empty box-shadow OR outline).
      const ring = await active.evaluate((el) => {
        const cs = window.getComputedStyle(el);
        return `${cs.outlineStyle}|${cs.boxShadow}`;
      });
      expect(ring).not.toBe('none|none');
    }
  });
});
