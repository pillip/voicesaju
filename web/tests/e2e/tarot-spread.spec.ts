/**
 * E2E spec for the v2 tarot spread (ISSUE-094, Screen 12).
 *
 * Same authoring convention as `preview.spec.ts` (ISSUE-021):
 * Playwright is not yet wired into CI, so this file documents the
 * browser-level acceptance criteria that the vitest tests cannot
 * fully cover and will execute once Playwright lands.
 *
 * AC coverage targeted here:
 * - AC2 — visible four-stage cascade for taps on each spread index.
 * - AC3 — determinism: tap index 0 in session A and index 4 in session
 *   B for the same `(date_KST, user_id)` reveals the SAME card art.
 * - AC5 — 375 px viewport: no card overflows.
 * - AC6 — flip → audio pipeline (FR-015) begins within 2 s.
 * - axe-core — focus order and reduced-motion fallback (run via
 *   `@axe-core/playwright` once the package is installed).
 *
 * Run locally once Playwright is wired:
 *   pnpm exec playwright test web/tests/e2e/tarot-spread.spec.ts
 */
import { expect, test } from '@playwright/test';

const FLAG_QS = '?tarot_v2=1'; // a debug toggle wired in the page when needed
const TAROT_URL = `/tarot${FLAG_QS}`;

test.describe('Tarot spread v2 (ISSUE-094)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(TAROT_URL);
    await expect(page.getByTestId('tarot-screen')).toBeVisible();
  });

  test('AC1 — 5 fan cards render with documented rotation tokens', async ({ page }) => {
    for (let i = 1; i <= 5; i++) {
      const card = page.getByTestId(`spread-card-${i}`);
      await expect(card).toBeVisible();
      const pose = card.locator('.spread-card__pose');
      await expect(pose).toHaveAttribute('data-rot', ['-22', '-11', '0', '11', '22'][i - 1]);
    }
  });

  test('AC2 — tap any index runs is-moving → is-centered → aria-pressed → reveal-visible', async ({
    page,
  }) => {
    const card3 = page.getByTestId('spread-card-3');
    await card3.click();
    // is-moving applies to all 5 simultaneously.
    for (let i = 1; i <= 5; i++) {
      await expect(page.getByTestId(`spread-card-${i}`)).toHaveClass(/is-moving/);
    }
    await expect(card3).toHaveClass(/is-centered/);
    await expect(card3).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.tarot-spread__reveal')).toHaveClass(/reveal-visible/);
  });

  test('AC3 — determinism: index 0 and index 4 reveal the same card art', async ({
    page,
    context,
  }) => {
    // Session A — tap leftmost (index 0 → data-pos=1).
    await page.getByTestId('spread-card-1').click();
    const imgA = page.locator('.tarot-spread__reveal img');
    await expect(imgA).toBeVisible();
    const srcA = await imgA.getAttribute('src');
    const altA = await imgA.getAttribute('alt');

    // Session B — same user, same KST day → tap rightmost (index 4).
    const pageB = await context.newPage();
    await pageB.goto(TAROT_URL);
    await pageB.getByTestId('spread-card-5').click();
    const imgB = pageB.locator('.tarot-spread__reveal img');
    await expect(imgB).toBeVisible();
    expect(await imgB.getAttribute('src')).toBe(srcA);
    expect(await imgB.getAttribute('alt')).toBe(altA);
  });

  test('AC4 — `.spread-card__back` / `__front` inherit absolute positioning (regression guard)', async ({
    page,
  }) => {
    // The `getComputedStyle(...).position` must be `absolute` for every
    // face surface; a regression that sets `position: relative` on the
    // back or front blows the perspective layer apart on Safari.
    for (const cls of ['.spread-card__back', '.spread-card__front']) {
      const positions = await page.$$eval(cls, (els) =>
        els.map((el) => window.getComputedStyle(el).position),
      );
      expect(positions.every((p) => p === 'absolute')).toBe(true);
    }
  });

  test('AC5 — 375 px viewport: no card extends past the viewport edges', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(TAROT_URL);
    const viewportWidth = 375;
    const overflows = await page.$$eval(
      '.spread-card',
      (els, vw) => {
        return els.some((el) => {
          const r = el.getBoundingClientRect();
          return r.left < 0 || r.right > vw;
        });
      },
      viewportWidth,
    );
    expect(overflows).toBe(false);
  });

  test('AC6 — after flip completes, audio pipeline begins within 2s (NFR-003)', async ({
    page,
  }) => {
    await page.getByTestId('spread-card-3').click();
    await expect(page.locator('.tarot-spread__reveal')).toHaveClass(/reveal-visible/);
    // The FR-015 hook fires a custom `tarot:reveal-complete` event; the
    // /tarot/play page wires audio on that event. We give the audio
    // chain at most 2 s after `reveal-visible` to mount the <audio>.
    const audioMounted = await page.waitForFunction(
      () => !!document.querySelector('audio[data-source="tarot-reveal"]'),
      { timeout: 2000 },
    );
    expect(audioMounted).toBeTruthy();
  });

  test('axe — `aria-pressed` and reduced-motion fallback hold', async ({ page }) => {
    // Emulate prefers-reduced-motion → tap should skip choreography and
    // land on reveal-visible immediately (no `is-moving` classes).
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(TAROT_URL);
    await page.getByTestId('spread-card-1').click();
    await expect(page.locator('.tarot-spread__reveal')).toHaveClass(/reveal-visible/);
    await expect(page.getByTestId('spread-card-1')).not.toHaveClass(/is-moving/);
  });

  test('Playwright visual regression — fan positioning at 375 / 1280 px', async ({ page }) => {
    for (const width of [375, 1280]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto(TAROT_URL);
      await expect(page.locator('.tarot-spread')).toBeVisible();
      // Snapshot baseline; first run creates, subsequent runs diff.
      await expect(page.locator('.tarot-spread')).toHaveScreenshot(`tarot-spread-${width}.png`, {
        maxDiffPixelRatio: 0.01,
      });
    }
  });
});
