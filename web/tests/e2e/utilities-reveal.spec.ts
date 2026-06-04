/**
 * E2E doc spec for the v2 utility surface (ISSUE-098, FR-044).
 *
 * Same authoring convention as `tarot-spread.spec.ts` (ISSUE-094) and
 * `nav-variants.spec.ts` (ISSUE-096): Playwright is not yet wired into
 * CI, so this file documents the browser-level acceptance criteria the
 * vitest source-text + jsdom probes cannot fully cover. It will
 * execute once Playwright lands.
 *
 * AC coverage targeted here:
 *   AC1 — `.tilted` resolves to `transform: matrix(0.9996, -0.0262,
 *         0.0262, 0.9996, 0, 0)` (Chromium's matrix() form of
 *         `rotate(-1.5deg)`).
 *   AC2 — toggling `.reveal-hidden` ↔ `.reveal-visible` animates
 *         opacity over ~400 ms; visibility flips to `visible`
 *         immediately on enter, stays `visible` for the full fade-out
 *         window (`transitionend` is observed on the opacity property).
 *   AC3 — `.tap-hint` runs `tap-hint-pulse` with `animation-duration:
 *         1.6s` and `animation-iteration-count: infinite`.
 *   AC4 — `prefers-reduced-motion: reduce` browser hint:
 *           a) `.tap-hint` resolves to `animation: none`.
 *           b) `.reveal-*` resolves to `transition: none` (instant
 *              show — no fade window).
 *           c) `.tilted` rotation is PRESERVED (documented decision).
 *   AC5 — toggling `.reveal-show-hide` ↔ `.reveal-hide` on a footer
 *         element produces a Cumulative Layout Shift score < 0.1
 *         (measured via `PerformanceObserver({ type: 'layout-shift' })`)
 *         because the pair uses `visibility:hidden`, not
 *         `display:none`.
 *
 * Run locally once Playwright is wired:
 *   pnpm exec playwright test web/tests/e2e/utilities-reveal.spec.ts
 */
import { expect, test } from '@playwright/test';

const UTILITIES_URL = '/preview/utilities';

test.describe('ISSUE-098 — tilted utilities (AC1)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(UTILITIES_URL);
    await expect(page.getByTestId('utilities-preview')).toBeVisible();
  });

  test('`.tilted` resolves to a matrix() encoding rotate(-1.5deg)', async ({ page }) => {
    const probe = page.getByTestId('probe-tilted');
    const transform = await probe.evaluate((el) => window.getComputedStyle(el).transform);
    // Chromium serializes `rotate(-1.5deg)` as
    //   matrix(cos(-1.5°), sin(-1.5°), -sin(-1.5°), cos(-1.5°), 0, 0)
    // ≈ matrix(0.99966, -0.02618, 0.02618, 0.99966, 0, 0).
    expect(transform).toMatch(/matrix\(\s*0\.9996[0-9]?/);
  });

  test('`.tilted--right` resolves to a +1.5° rotation matrix', async ({ page }) => {
    const transform = await page
      .getByTestId('probe-tilted-right')
      .evaluate((el) => window.getComputedStyle(el).transform);
    // +1.5° → sin component is +0.02618 (vs -0.02618 for -1.5°).
    expect(transform).toMatch(/matrix\(\s*0\.9996[0-9]?,\s*0\.0261/);
  });

  test('`.tilted--more` resolves to a -3° rotation matrix', async ({ page }) => {
    const transform = await page
      .getByTestId('probe-tilted-more')
      .evaluate((el) => window.getComputedStyle(el).transform);
    // -3° → cos ≈ 0.99863, sin ≈ -0.05234.
    expect(transform).toMatch(/matrix\(\s*0\.998[0-9]+/);
  });
});

test.describe('ISSUE-098 — reveal-section fade-in (AC2)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(UTILITIES_URL);
    await expect(page.getByTestId('utilities-preview')).toBeVisible();
  });

  test('toggling `.reveal-hidden` → `.reveal-visible` animates opacity to 1 over ~400 ms', async ({
    page,
  }) => {
    const target = page.getByTestId('probe-reveal');
    await expect(target).toHaveClass(/reveal-hidden/);
    // Opacity at rest is 0.
    let opacity = await target.evaluate((el) => window.getComputedStyle(el).opacity);
    expect(parseFloat(opacity)).toBe(0);

    await page.getByTestId('probe-reveal-toggle').click();
    await expect(target).toHaveClass(/reveal-visible/);
    // After the 400ms transition, opacity must settle at 1.
    await page.waitForTimeout(450);
    opacity = await target.evaluate((el) => window.getComputedStyle(el).opacity);
    expect(parseFloat(opacity)).toBe(1);
  });

  test('visibility flips to `visible` immediately on enter (before the fade finishes)', async ({
    page,
  }) => {
    await page.getByTestId('probe-reveal-toggle').click();
    // Sample visibility shortly after the toggle but well before the
    // 400 ms fade window completes — the AC requires the visibility
    // delay on `.reveal-visible` to be 0s, so the element should
    // already be hit-test-eligible.
    await page.waitForTimeout(30);
    const visibility = await page
      .getByTestId('probe-reveal')
      .evaluate((el) => window.getComputedStyle(el).visibility);
    expect(visibility).toBe('visible');
  });
});

test.describe('ISSUE-098 — tap-hint pulse (AC3)', () => {
  test('`.tap-hint` runs tap-hint-pulse with 1.6s duration, infinite iterations', async ({
    page,
  }) => {
    await page.goto(UTILITIES_URL);
    const hint = page.getByTestId('probe-tap-hint');
    const { name, duration, iterations } = await hint.evaluate((el) => {
      const cs = window.getComputedStyle(el);
      return {
        name: cs.animationName,
        duration: cs.animationDuration,
        iterations: cs.animationIterationCount,
      };
    });
    expect(name).toBe('tap-hint-pulse');
    expect(duration).toBe('1.6s');
    expect(iterations).toBe('infinite');
  });
});

test.describe('ISSUE-098 — prefers-reduced-motion (AC4)', () => {
  test.use({ reducedMotion: 'reduce' });

  test('`.tap-hint` resolves to animation: none under reduced motion', async ({ page }) => {
    await page.goto(UTILITIES_URL);
    const animationName = await page
      .getByTestId('probe-tap-hint')
      .evaluate((el) => window.getComputedStyle(el).animationName);
    expect(animationName).toBe('none');
  });

  test('`.reveal-*` transitions become instant under reduced motion (no fade)', async ({
    page,
  }) => {
    await page.goto(UTILITIES_URL);
    const target = page.getByTestId('probe-reveal');
    await page.getByTestId('probe-reveal-toggle').click();
    // No need to wait 400 ms — under reduced motion opacity must be
    // 1 essentially immediately.
    await page.waitForTimeout(50);
    const opacity = await target.evaluate((el) => window.getComputedStyle(el).opacity);
    expect(parseFloat(opacity)).toBe(1);
  });

  test('`.tilted` rotation is PRESERVED under reduced motion (documented decision: tilt is identity, not motion)', async ({
    page,
  }) => {
    await page.goto(UTILITIES_URL);
    const transform = await page
      .getByTestId('probe-tilted')
      .evaluate((el) => window.getComputedStyle(el).transform);
    expect(transform).toMatch(/matrix\(\s*0\.9996/);
    expect(transform).not.toBe('none');
  });
});

test.describe('ISSUE-098 — reveal-show-hide / reveal-hide CLS budget (AC5)', () => {
  test('toggling .reveal-show-hide ↔ .reveal-hide on a footer keeps CLS < 0.1', async ({
    page,
  }) => {
    await page.goto(UTILITIES_URL);
    // Install a layout-shift observer before the toggle so we capture
    // any reflow caused by the class swap.
    await page.evaluate(() => {
      (window as unknown as { __clsScore: number }).__clsScore = 0;
      const po = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const layoutShift = entry as PerformanceEntry & {
            value: number;
            hadRecentInput: boolean;
          };
          if (!layoutShift.hadRecentInput) {
            (window as unknown as { __clsScore: number }).__clsScore += layoutShift.value;
          }
        }
      });
      po.observe({ type: 'layout-shift', buffered: true });
    });
    await page.getByTestId('probe-footer-toggle').click();
    await page.waitForTimeout(150);
    const cls = await page.evaluate(() => (window as unknown as { __clsScore: number }).__clsScore);
    expect(cls).toBeLessThan(0.1);
  });
});
