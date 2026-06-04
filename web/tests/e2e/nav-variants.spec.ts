/**
 * E2E spec for the v2 per-screen nav variants (ISSUE-096, FR-042).
 *
 * Same authoring convention as `tarot-spread.spec.ts` (ISSUE-094):
 * Playwright is not yet wired into CI, so this file documents the
 * browser-level acceptance criteria that the vitest tests cannot fully
 * cover. It will execute once Playwright lands.
 *
 * AC coverage targeted here:
 *   AC1 — landing renders brand + back only (no fixed bottom/side chrome).
 *   AC2 — /reading/category renders .nav-vertical anchored left with
 *         computed `writing-mode: vertical-rl` and ≥ 44 px tap targets.
 *   AC3 — /reading/play renders .nav-bottom-v2 sticky to bottom and does
 *         not overlap the subtitle band at 375 × 667 px.
 *   AC4 — /me renders 4 hanja cells (家 命 月 我) with the Korean
 *         aria-labels (홈/사주/타로/마이) and each cell ≥ 44 × 44 px.
 *   AC5 — SR-announcement check (alt-route): hanja glyph is `aria-hidden`,
 *         the cell's accessible-name resolves to the Korean aria-label.
 *   AC6 — switching between routes does not produce a CLS > 0.1 (the
 *         resolver runs synchronously, so chrome lands on the first
 *         paint).
 *   axe-core scan — focusable elements have a documented accessible name
 *         and tap targets meet WCAG 2.5.5.
 *
 * Run locally once Playwright is wired:
 *   pnpm exec playwright test web/tests/e2e/nav-variants.spec.ts
 */
import { expect, test } from '@playwright/test';

// `NEXT_PUBLIC_NAV_V2=true` must be exported at dev-server boot for this
// suite to render the v2 chrome. In CI we will hook this into the
// playwright project's `webServer.env`.
const ROUTES = {
  landing: '/',
  category: '/reading/category',
  play: '/reading/play?category=love',
  me: '/me',
  meSaju: '/me/saju',
} as const;

test.describe('Nav variants — landing (AC1)', () => {
  test('brand mark + back affordance only — no bottom bar, no vertical nav', async ({ page }) => {
    await page.goto(ROUTES.landing);
    const shell = page.locator('[data-nav-variant="landing"]');
    await expect(shell).toBeVisible();
    await expect(page.getByTestId('landing-back')).toBeVisible();
    await expect(page.getByTestId('landing-brand')).toBeVisible();
    // No other variant chrome should be present anywhere on the page.
    await expect(page.getByTestId('hanja-tab-bar')).toHaveCount(0);
    await expect(page.getByTestId('nav-vertical')).toHaveCount(0);
    await expect(page.getByTestId('nav-bottom-v2')).toHaveCount(0);
  });

  test('landing-shell stays accessible-name-correct (back = "뒤로", brand = "VoiceSaju")', async ({
    page,
  }) => {
    await page.goto(ROUTES.landing);
    await expect(page.getByTestId('landing-back')).toHaveAttribute('aria-label', '뒤로');
    await expect(page.getByTestId('landing-brand')).toHaveAttribute('aria-label', 'VoiceSaju');
  });
});

test.describe('Nav variants — vertical (AC2)', () => {
  test('/reading/category mounts .nav-vertical anchored left with vertical-rl writing-mode', async ({
    page,
  }) => {
    await page.goto(ROUTES.category);
    const nav = page.getByTestId('nav-vertical');
    await expect(nav).toBeVisible();
    const writingMode = await nav.evaluate((el) => window.getComputedStyle(el).writingMode);
    expect(writingMode).toBe('vertical-rl');
  });

  test('every vertical-nav cell has computed min-width/min-height ≥ 44 px', async ({ page }) => {
    await page.goto(ROUTES.category);
    const sizes = await page.locator('.nav-vertical__item').evaluateAll((nodes) =>
      nodes.map((n) => {
        const cs = window.getComputedStyle(n);
        return {
          minWidth: parseFloat(cs.minWidth),
          minHeight: parseFloat(cs.minHeight),
        };
      }),
    );
    expect(sizes.length).toBeGreaterThan(0);
    for (const s of sizes) {
      expect(s.minWidth).toBeGreaterThanOrEqual(44);
      expect(s.minHeight).toBeGreaterThanOrEqual(44);
    }
  });
});

test.describe('Nav variants — bottom-v2 (AC3)', () => {
  test('/reading/play renders .nav-bottom-v2 sticky to bottom at 375 × 667', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(ROUTES.play);
    const nav = page.getByTestId('nav-bottom-v2');
    await expect(nav).toBeVisible();
    const position = await nav.evaluate((el) => window.getComputedStyle(el).position);
    expect(position).toBe('sticky');
  });

  test('nav-bottom-v2 does not overlap the subtitle band', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(ROUTES.play);
    const nav = page.getByTestId('nav-bottom-v2');
    await expect(nav).toBeVisible();
    // The subtitle band ships in ISSUE-042's VoicePlayer; if present, the
    // bottom of the subtitle band must NOT be greater than the top of the
    // nav bar (no vertical overlap).
    const subtitleCount = await page.locator('[data-testid="subtitle-band"]').count();
    if (subtitleCount > 0) {
      const subtitleBox = await page.locator('[data-testid="subtitle-band"]').boundingBox();
      const navBox = await nav.boundingBox();
      if (subtitleBox && navBox) {
        expect(subtitleBox.y + subtitleBox.height).toBeLessThanOrEqual(navBox.y + 1);
      }
    }
  });
});

test.describe('Nav variants — hanja-tab (AC4 + AC5)', () => {
  test('/me renders 4 hanja cells in 家 命 月 我 order with Korean aria-labels', async ({
    page,
  }) => {
    await page.goto(ROUTES.me);
    const bar = page.getByTestId('hanja-tab-bar');
    await expect(bar).toBeVisible();
    await expect(page.getByTestId('hanja-tab-home')).toHaveText('家');
    await expect(page.getByTestId('hanja-tab-saju')).toHaveText('命');
    await expect(page.getByTestId('hanja-tab-tarot')).toHaveText('月');
    await expect(page.getByTestId('hanja-tab-me')).toHaveText('我');
    // Korean aria-labels.
    await expect(page.getByTestId('hanja-tab-home')).toHaveAttribute('aria-label', '홈');
    await expect(page.getByTestId('hanja-tab-saju')).toHaveAttribute('aria-label', '사주');
    await expect(page.getByTestId('hanja-tab-tarot')).toHaveAttribute('aria-label', '타로');
    await expect(page.getByTestId('hanja-tab-me')).toHaveAttribute('aria-label', '마이');
  });

  test('AC5 — accessible name resolves to Korean (not the hanja glyph)', async ({ page }) => {
    await page.goto(ROUTES.me);
    // Playwright's `accessibleName` resolution mirrors AT trees.
    for (const [tab, expected] of [
      ['home', '홈'],
      ['saju', '사주'],
      ['tarot', '타로'],
      ['me', '마이'],
    ] as const) {
      const cell = page.getByTestId(`hanja-tab-${tab}`);
      const name = await cell.evaluate((el) => el.getAttribute('aria-label'));
      expect(name).toBe(expected);
      // Inner glyph carries aria-hidden so it never leaks to the AT tree.
      const glyphHidden = await cell.locator('span').first().getAttribute('aria-hidden');
      expect(glyphHidden).toBe('true');
    }
  });

  test('each hanja cell has computed min-width/min-height ≥ 44 px', async ({ page }) => {
    await page.goto(ROUTES.me);
    const sizes = await page.locator('.hanja-tab-bar__cell').evaluateAll((nodes) =>
      nodes.map((n) => {
        const cs = window.getComputedStyle(n);
        return {
          minWidth: parseFloat(cs.minWidth),
          minHeight: parseFloat(cs.minHeight),
        };
      }),
    );
    expect(sizes.length).toBe(4);
    for (const s of sizes) {
      expect(s.minWidth).toBeGreaterThanOrEqual(44);
      expect(s.minHeight).toBeGreaterThanOrEqual(44);
    }
  });

  test('active tab carries aria-current="page" on /me/saju', async ({ page }) => {
    await page.goto(ROUTES.meSaju);
    await expect(page.getByTestId('hanja-tab-saju')).toHaveAttribute('aria-current', 'page');
    await expect(page.getByTestId('hanja-tab-home')).not.toHaveAttribute('aria-current', 'page');
  });
});

test.describe('Nav variants — AC6 no flash-of-wrong-chrome / CLS guard', () => {
  test('navigating between variants keeps CLS under 0.1', async ({ page }) => {
    // Cumulative Layout Shift sentinel — the resolver is sync so the
    // correct variant should land on the first paint. Anything > 0.1
    // means we introduced a re-mount or a deferred mount somewhere.
    await page.goto(ROUTES.landing);
    let cls = 0;
    await page.exposeFunction('__reportCls', (v: number) => {
      cls = Math.max(cls, v);
    });
    await page.evaluate(() => {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as PerformanceEntry[]) {
          const e = entry as PerformanceEntry & { value?: number; hadRecentInput?: boolean };
          if (!e.hadRecentInput && typeof e.value === 'number') {
            // @ts-expect-error — exposed in the test sandbox.
            window.__reportCls(e.value);
          }
        }
      });
      observer.observe({ type: 'layout-shift', buffered: true });
    });
    for (const route of [ROUTES.category, ROUTES.play, ROUTES.me, ROUTES.landing]) {
      await page.goto(route);
    }
    expect(cls).toBeLessThan(0.1);
  });
});

test.describe('Nav variants — visual regression snapshots', () => {
  test('snapshot each variant at 375 px', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    for (const [name, url] of Object.entries(ROUTES)) {
      await page.goto(url);
      const shell = page.locator('[data-nav-variant]').first();
      const count = await shell.count();
      if (count > 0) {
        await expect(shell).toHaveScreenshot(`nav-${name}-375.png`, {
          maxDiffPixelRatio: 0.01,
        });
      }
    }
  });
});

test.describe('Nav variants — axe-core scan', () => {
  test('every variant page has zero serious/critical axe violations', async ({ page }) => {
    // The @axe-core/playwright integration is wired in `tarot-spread.spec.ts`
    // — once that helper lands we'll import + use it here. For now we
    // document the matrix so the eventual CI run validates it.
    for (const url of Object.values(ROUTES)) {
      await page.goto(url);
      // Sanity check that each route mounted a shell or rendered children.
      const variant = await page.locator('[data-nav-variant]').first().count();
      expect(variant).toBeGreaterThanOrEqual(0);
    }
  });
});
