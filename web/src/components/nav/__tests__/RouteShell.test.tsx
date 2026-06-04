/**
 * ISSUE-096 — RouteShell rendering + a11y tests.
 *
 * Coverage map vs AC:
 *   AC1 (landing) — landing variant renders brand mark + back button only
 *                   (no bottom bar, no vertical nav).
 *   AC2 (vertical) — vertical variant renders .nav-vertical anchored left
 *                    with tap targets ≥ 44 px.
 *   AC3 (bottom-v2) — bottom-v2 renders sticky .nav-bottom-v2 at the
 *                     bottom slot, does NOT render any of the other variants.
 *   AC4 (hanja tab bar) — 4 hanja cells with aria-labels, 44 px tap target.
 *   AC5 (SR copy) — aria-labels are 홈/사주/타로/마이; the visible hanja
 *                   is `aria-hidden` so SRs do not announce it.
 *   AC6 (no flash) — resolver is sync (covered in navVariant.test.ts);
 *                    here we assert the shell mounts the right variant on
 *                    the FIRST render for every documented pathname.
 *
 * Flag rollback — `NEXT_PUBLIC_NAV_V2=false` short-circuits the shell so
 * children render alone (no `data-nav-variant` attribute on the DOM).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

// Mock next/navigation so we can drive `usePathname()` per test case.
const { usePathnameMock } = vi.hoisted(() => ({
  usePathnameMock: vi.fn((): string => '/'),
}));

vi.mock('next/navigation', () => ({
  usePathname: usePathnameMock,
}));

import { RouteShell } from '../RouteShell';

const NAV_ENV_KEY = 'NEXT_PUBLIC_NAV_V2';

beforeEach(() => {
  process.env[NAV_ENV_KEY] = 'true';
  usePathnameMock.mockReset();
  usePathnameMock.mockReturnValue('/');
});

afterEach(() => {
  delete process.env[NAV_ENV_KEY];
});

describe('RouteShell — flag gate (rollback)', () => {
  it('renders children as-is when NEXT_PUBLIC_NAV_V2 is unset (AC rollback)', () => {
    delete process.env[NAV_ENV_KEY];
    usePathnameMock.mockReturnValue('/me');
    render(
      <RouteShell>
        <p data-testid="page-content">page</p>
      </RouteShell>,
    );
    expect(screen.getByTestId('page-content')).toBeTruthy();
    // NO v2 chrome should leak when the flag is off.
    expect(screen.queryByTestId('hanja-tab-bar')).toBeNull();
    expect(screen.queryByTestId('nav-vertical')).toBeNull();
    expect(screen.queryByTestId('nav-bottom-v2')).toBeNull();
  });

  it('renders children as-is when flag is explicitly false', () => {
    process.env[NAV_ENV_KEY] = 'false';
    usePathnameMock.mockReturnValue('/reading/category');
    render(
      <RouteShell>
        <p data-testid="page-content">page</p>
      </RouteShell>,
    );
    expect(screen.queryByTestId('nav-vertical')).toBeNull();
  });
});

describe('RouteShell — landing variant (AC1)', () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue('/');
  });

  it('renders brand mark + back affordance only', () => {
    render(
      <RouteShell>
        <main data-testid="landing-content">hi</main>
      </RouteShell>,
    );
    const root = screen.getByTestId('landing-content').parentElement;
    expect(root?.getAttribute('data-nav-variant')).toBe('landing');
    expect(screen.getByTestId('landing-back')).toBeTruthy();
    expect(screen.getByTestId('landing-brand')).toBeTruthy();
    // No other v2 chrome should be present.
    expect(screen.queryByTestId('hanja-tab-bar')).toBeNull();
    expect(screen.queryByTestId('nav-vertical')).toBeNull();
    expect(screen.queryByTestId('nav-bottom-v2')).toBeNull();
  });

  it('back button has Korean aria-label', () => {
    render(
      <RouteShell>
        <p>p</p>
      </RouteShell>,
    );
    expect(screen.getByTestId('landing-back').getAttribute('aria-label')).toBe('뒤로');
  });
});

describe('RouteShell — vertical variant (AC2)', () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue('/reading/category');
  });

  it('mounts .nav-vertical with the default category anchors', () => {
    render(
      <RouteShell>
        <section data-testid="cat-page">cat</section>
      </RouteShell>,
    );
    const nav = screen.getByTestId('nav-vertical');
    expect(nav.className).toContain('nav-vertical');
    // Default category anchors per docs/wireframes.md.
    expect(within(nav).getByText('연애')).toBeTruthy();
    expect(within(nav).getByText('직장')).toBeTruthy();
    expect(within(nav).getByText('금전')).toBeTruthy();
  });

  it('uses caller-supplied verticalItems when provided', () => {
    render(
      <RouteShell verticalItems={[{ label: '커스텀', href: '/reading/intro/love' }]}>
        <section>cat</section>
      </RouteShell>,
    );
    const nav = screen.getByTestId('nav-vertical');
    expect(within(nav).getByText('커스텀')).toBeTruthy();
    expect(within(nav).queryByText('연애')).toBeNull();
  });

  it('every cell carries the .nav-vertical__item class for the 44 px tap-target rule', () => {
    render(
      <RouteShell>
        <section>cat</section>
      </RouteShell>,
    );
    const cells = screen.getAllByTestId(/^nav-vertical-/);
    expect(cells.length).toBe(3);
    for (const cell of cells) {
      expect(cell.className).toContain('nav-vertical__item');
    }
  });
});

describe('RouteShell — bottom-v2 variant (AC3)', () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue('/reading/play');
  });

  it('mounts .nav-bottom-v2 below the page content', () => {
    render(
      <RouteShell>
        <section data-testid="play-page">play</section>
      </RouteShell>,
    );
    const root = screen.getByTestId('play-page').parentElement?.parentElement;
    expect(root?.getAttribute('data-nav-variant')).toBe('bottom-v2');
    const nav = screen.getByTestId('nav-bottom-v2');
    expect(nav.className).toContain('nav-bottom-v2');
    // 메뉴 + 종료 affordances are present.
    expect(screen.getByTestId('nav-bottom-v2-menu')).toBeTruthy();
    expect(screen.getByTestId('nav-bottom-v2-exit')).toBeTruthy();
  });

  it('does NOT render any other variant chrome on /reading/play', () => {
    render(
      <RouteShell>
        <section>play</section>
      </RouteShell>,
    );
    expect(screen.queryByTestId('hanja-tab-bar')).toBeNull();
    expect(screen.queryByTestId('nav-vertical')).toBeNull();
    expect(screen.queryByTestId('landing-back')).toBeNull();
  });

  it('also activates on nested play sub-routes', () => {
    usePathnameMock.mockReturnValue('/reading/play/followup');
    render(
      <RouteShell>
        <section>p</section>
      </RouteShell>,
    );
    expect(screen.getByTestId('nav-bottom-v2')).toBeTruthy();
  });
});

describe('RouteShell — hanja-tab variant (AC4 + AC5)', () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue('/me');
  });

  it('renders 4 hanja tabs in the 家 命 月 我 order', () => {
    render(
      <RouteShell>
        <section data-testid="me-page">me</section>
      </RouteShell>,
    );
    const bar = screen.getByTestId('hanja-tab-bar');
    expect(bar.className).toContain('hanja-tab-bar');
    expect(screen.getByTestId('hanja-tab-home').textContent).toBe('家');
    expect(screen.getByTestId('hanja-tab-saju').textContent).toBe('命');
    expect(screen.getByTestId('hanja-tab-tarot').textContent).toBe('月');
    expect(screen.getByTestId('hanja-tab-me').textContent).toBe('我');
  });

  it('each tab carries a Korean aria-label (NOT the hanja character) — AC5', () => {
    render(
      <RouteShell>
        <section>me</section>
      </RouteShell>,
    );
    expect(screen.getByTestId('hanja-tab-home').getAttribute('aria-label')).toBe('홈');
    expect(screen.getByTestId('hanja-tab-saju').getAttribute('aria-label')).toBe('사주');
    expect(screen.getByTestId('hanja-tab-tarot').getAttribute('aria-label')).toBe('타로');
    expect(screen.getByTestId('hanja-tab-me').getAttribute('aria-label')).toBe('마이');
  });

  it('the visible hanja glyph is aria-hidden so SRs only announce the Korean label', () => {
    render(
      <RouteShell>
        <section>me</section>
      </RouteShell>,
    );
    const tab = screen.getByTestId('hanja-tab-home');
    const glyph = tab.querySelector('span');
    expect(glyph?.getAttribute('aria-hidden')).toBe('true');
  });

  it('hrefs match the spec: /me, /me/saju, /tarot, /me/account', () => {
    render(
      <RouteShell>
        <section>me</section>
      </RouteShell>,
    );
    expect(screen.getByTestId('hanja-tab-home').getAttribute('href')).toBe('/me');
    expect(screen.getByTestId('hanja-tab-saju').getAttribute('href')).toBe('/me/saju');
    expect(screen.getByTestId('hanja-tab-tarot').getAttribute('href')).toBe('/tarot');
    expect(screen.getByTestId('hanja-tab-me').getAttribute('href')).toBe('/me/account');
  });

  it('marks the active tab with aria-current="page" based on pathname', () => {
    usePathnameMock.mockReturnValue('/me/saju');
    render(
      <RouteShell>
        <section>me</section>
      </RouteShell>,
    );
    expect(screen.getByTestId('hanja-tab-saju').getAttribute('aria-current')).toBe('page');
    expect(screen.getByTestId('hanja-tab-home').getAttribute('aria-current')).toBeNull();
  });

  it('every cell carries the .hanja-tab-bar__cell class for the 44 px tap-target rule', () => {
    render(
      <RouteShell>
        <section>me</section>
      </RouteShell>,
    );
    for (const key of ['home', 'saju', 'tarot', 'me']) {
      const cell = screen.getByTestId(`hanja-tab-${key}`);
      expect(cell.className).toContain('hanja-tab-bar__cell');
    }
  });
});

describe('RouteShell — variant resolution across pathnames (AC6 sync render)', () => {
  it.each([
    ['/', 'landing'],
    ['/reading/category', 'vertical'],
    ['/reading/play', 'bottom-v2'],
    ['/reading/play/followup', 'bottom-v2'],
    ['/me', 'hanja-tab'],
    ['/me/saju', 'hanja-tab'],
    ['/me/history', 'hanja-tab'],
  ] as const)('mounts variant=%s for pathname %s on first render', (path, expected) => {
    usePathnameMock.mockReturnValue(path);
    const { container } = render(
      <RouteShell>
        <p>x</p>
      </RouteShell>,
    );
    const variantEl = container.querySelector('[data-nav-variant]');
    expect(variantEl?.getAttribute('data-nav-variant')).toBe(expected);
  });

  it('renders children alone (no data-nav-variant) on unmapped routes', () => {
    usePathnameMock.mockReturnValue('/auth/login');
    const { container } = render(
      <RouteShell>
        <p data-testid="auth-page">login</p>
      </RouteShell>,
    );
    expect(container.querySelector('[data-nav-variant]')).toBeNull();
    expect(screen.getByTestId('auth-page')).toBeTruthy();
  });

  it('honours `override` prop over pathname resolution', () => {
    usePathnameMock.mockReturnValue('/me');
    const { container } = render(
      <RouteShell override="default">
        <p data-testid="not-found">404</p>
      </RouteShell>,
    );
    // override=default short-circuits — no variant chrome.
    expect(container.querySelector('[data-nav-variant]')).toBeNull();
    expect(screen.queryByTestId('hanja-tab-bar')).toBeNull();
  });
});

describe('RouteShell — a11y (axe-core)', () => {
  const axeRules = {
    // CSS classes use tokens (--cream-300 on --hanji-900) that jsdom can't
    // resolve, so colour-contrast scoring is meaningless here.
    'color-contrast': { enabled: false },
    // The .nav-vertical container is sticky-positioned via vertical-rl —
    // jsdom layout doesn't matter for landmark-unique scoring.
    region: { enabled: false },
  };

  it('hanja-tab variant has zero axe violations', async () => {
    usePathnameMock.mockReturnValue('/me');
    const { container } = render(
      <RouteShell>
        <main>me</main>
      </RouteShell>,
    );
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it('vertical variant has zero axe violations', async () => {
    usePathnameMock.mockReturnValue('/reading/category');
    const { container } = render(
      <RouteShell>
        <main>cat</main>
      </RouteShell>,
    );
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it('bottom-v2 variant has zero axe violations', async () => {
    usePathnameMock.mockReturnValue('/reading/play');
    const { container } = render(
      <RouteShell>
        <main>play</main>
      </RouteShell>,
    );
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it('landing variant has zero axe violations', async () => {
    usePathnameMock.mockReturnValue('/');
    const { container } = render(
      <RouteShell>
        <main>landing</main>
      </RouteShell>,
    );
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
