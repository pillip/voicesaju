'use client';

/**
 * ISSUE-096 — RouteShell: per-screen v2 navigation chrome dispatcher.
 *
 * Wraps a page (typically from a route-group `layout.tsx`) and mounts the
 * correct v2 chrome based on the current pathname:
 *
 *   /                  → landing-shell  (brand-mark top-right + back top-left)
 *   /reading/category  → .nav-vertical  (vertical-rl, anchored left, 44 px tap)
 *   /reading/play      → .nav-bottom-v2 (sticky bottom, immersive)
 *   /me, /me/*         → .hanja-tab-bar (4 hanja tabs 家 命 月 我)
 *   everything else    → default        (children only, no v2 chrome)
 *
 * Wiring contract:
 *   - This component is mounted at the leaf route layouts (NOT root layout)
 *     so the variant resolves correctly without polluting global pages.
 *   - Resolution runs synchronously off `usePathname()` so React commits the
 *     correct variant in the FIRST paint — that's how we satisfy AC6 (no
 *     flash-of-wrong-chrome, CLS < 0.1). The pure resolver is unit-tested
 *     in `navVariant.test.ts`.
 *   - When `NEXT_PUBLIC_NAV_V2` is false / unset (production default), this
 *     component is a pass-through: it renders children with NO v2 class
 *     hooks so the existing v1 `TopAppBar`/`BottomTabBar` chrome on each
 *     page remains the only nav. The rollback path documented on the
 *     issue (`NAV_V2=false`) IS this branch.
 *   - The `override` prop lets exceptional screens (404, error.tsx) opt
 *     out of variant resolution and force a specific variant — for the
 *     404 we pass `override="default"` so the framework's not-found page
 *     never inherits e.g. the hanja tab bar from its sibling route.
 *
 * `nav-v2.css` is imported here (not in globals.css) so the v2 styles only
 * land in bundles that actually mount this component. When the feature
 * flag is off we still import the CSS — that's ~2 KB, all selectors are
 * scoped under the v2 class names, and zero of those classes ship to the
 * DOM in the off-branch. Net cost: paint-time CSS parse only.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

import { isNavV2Enabled } from '@/lib/featureFlags';
import { activeHanjaTabKey, HANJA_TABS, resolveNavVariant, type NavVariant } from './navVariant';

import '@/styles/nav-v2.css';

export interface RouteShellProps {
  /** Page content wrapped by the shell. */
  children: ReactNode;
  /**
   * Force a specific variant (skips pathname resolution).
   *
   * Use cases:
   *   - 404 / error boundaries that should never wear a variant chrome.
   *   - Preview pages where we want to show a specific variant deliberately.
   *
   * When `'default'` is passed, the shell renders children as-is.
   */
  override?: NavVariant;
  /**
   * Optional category labels for the vertical nav. The category nav is
   * intentionally low-magic — callers pass their own list because the
   * routes change per category. Empty list → no anchors (still renders
   * the column for the friction-pause aesthetic).
   */
  verticalItems?: ReadonlyArray<{ label: string; href: string }>;
}

/**
 * The default vertical-nav anchors for `/reading/category`. Pulled from
 * `docs/wireframes.md` §"Category screen": love · work · money.
 * Consumers can override via `verticalItems`.
 */
const DEFAULT_VERTICAL_ITEMS: ReadonlyArray<{ label: string; href: string }> = [
  { label: '연애', href: '/reading/intro/love' },
  { label: '직장', href: '/reading/intro/work' },
  { label: '금전', href: '/reading/intro/money' },
];

export function RouteShell({ children, override, verticalItems }: RouteShellProps) {
  const pathname = usePathname() ?? '/';
  const flagEnabled = isNavV2Enabled();

  // Rollback short-circuit. We intentionally evaluate the flag AFTER the
  // hook call so React's hook ordering stays stable across renders.
  if (!flagEnabled) {
    return <>{children}</>;
  }

  const variant: NavVariant = override ?? resolveNavVariant(pathname);

  if (variant === 'default') {
    return <>{children}</>;
  }

  if (variant === 'landing') {
    return (
      <div data-nav-variant="landing" className="relative">
        <LandingShell />
        {children}
      </div>
    );
  }

  if (variant === 'vertical') {
    return (
      <div data-nav-variant="vertical" className="flex min-h-screen flex-row">
        <VerticalNav items={verticalItems ?? DEFAULT_VERTICAL_ITEMS} pathname={pathname} />
        <div className="flex-1">{children}</div>
      </div>
    );
  }

  if (variant === 'bottom-v2') {
    return (
      <div data-nav-variant="bottom-v2" className="flex min-h-screen flex-col">
        <div className="flex-1">{children}</div>
        <BottomV2Nav />
      </div>
    );
  }

  // variant === 'hanja-tab'
  return (
    <div data-nav-variant="hanja-tab" className="flex min-h-screen flex-col">
      <div className="flex-1 pb-[64px]">{children}</div>
      <MyPageTabBar pathname={pathname} />
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Sub-components
 * ------------------------------------------------------------------ */

/**
 * Landing chrome — brand mark top-right + back affordance top-left.
 *
 * No bottom bar, no fixed side nav (AC1: "only brand mark and back").
 * The back affordance routes to `/` itself — on the landing page, the
 * historic browser back is the most useful behaviour; we expose it as a
 * styled `<button>` so it works even when there's no referrer (PWA cold
 * start) by falling back to `history.back()`.
 */
function LandingShell() {
  return (
    <div className="nav-landing-shell" role="navigation" aria-label="랜딩 chrome">
      <button
        type="button"
        className="nav-landing-shell__back"
        aria-label="뒤로"
        onClick={() => {
          if (typeof window !== 'undefined' && window.history.length > 1) {
            window.history.back();
          }
        }}
        data-testid="landing-back"
      >
        ←
      </button>
      <span className="nav-landing-shell__brand" data-testid="landing-brand" aria-label="VoiceSaju">
        VoiceSaju
      </span>
    </div>
  );
}

/**
 * Vertical nav — used on `/reading/category` only.
 *
 * The container uses `writing-mode: vertical-rl` via the `.nav-vertical`
 * class (in nav-v2.css) for the intentional Toss-funnel friction.
 * Each cell is wrapped in a Link so the SSR-friendly `<a>` is preserved.
 */
function VerticalNav({
  items,
  pathname,
}: {
  items: ReadonlyArray<{ label: string; href: string }>;
  pathname: string;
}) {
  return (
    <nav className="nav-vertical" aria-label="카테고리 nav" data-testid="nav-vertical">
      <ul className="flex list-none flex-col gap-s4 p-0">
        {items.map((item) => {
          const isActive = pathname === item.href;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={'nav-vertical__item' + (isActive ? ' nav-vertical__item--active' : '')}
                aria-current={isActive ? 'page' : undefined}
                data-testid={`nav-vertical-${item.href}`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * Bottom v2 nav — used on `/reading/play` only.
 *
 * Stick-to-bottom strip with a translucent hanji backdrop. We deliberately
 * keep the action set minimal so it never overlaps the subtitle band (AC3
 * — 375 px height). Only two affordances: a "menu" (drawer trigger) on the
 * left and a "exit" on the right. The drawer/exit modal wiring is the
 * page's responsibility; this component just provides the chrome surface
 * with stable test ids so behavioural tests can pin without an internal
 * implementation lock.
 */
function BottomV2Nav() {
  return (
    <nav className="nav-bottom-v2" aria-label="reading nav" data-testid="nav-bottom-v2">
      <Link
        href="/me"
        className="nav-bottom-v2__cell"
        aria-label="메뉴"
        data-testid="nav-bottom-v2-menu"
      >
        ☰
      </Link>
      <Link
        href="/reading/end"
        className="nav-bottom-v2__cell"
        aria-label="종료"
        data-testid="nav-bottom-v2-exit"
      >
        ✕
      </Link>
    </nav>
  );
}

/**
 * MyPageTabBar — 4 hanja tabs `家 命 月 我` bottom-pinned (used on `/me/*`).
 *
 * AC4 + AC5 mapping:
 *   - Each cell is ≥ 44 × 44 px via `.hanja-tab-bar__cell`.
 *   - `aria-label` carries the Korean reading (홈/사주/타로/마이) so
 *     screen readers announce the Korean, NOT the hanja character.
 *   - The visible hanja glyph is wrapped in `aria-hidden` so it never
 *     leaks into the AT tree.
 */
function MyPageTabBar({ pathname }: { pathname: string }) {
  const activeKey = activeHanjaTabKey(pathname);
  return (
    <nav className="hanja-tab-bar" aria-label="마이 페이지 메뉴" data-testid="hanja-tab-bar">
      {HANJA_TABS.map((tab) => {
        const isActive = activeKey === tab.key;
        return (
          <Link
            key={tab.key}
            href={tab.href}
            aria-label={tab.ariaLabel}
            aria-current={isActive ? 'page' : undefined}
            className={'hanja-tab-bar__cell' + (isActive ? ' hanja-tab-bar__cell--active' : '')}
            data-testid={`hanja-tab-${tab.key}`}
            data-tab-key={tab.key}
          >
            <span aria-hidden="true">{tab.hanja}</span>
          </Link>
        );
      })}
    </nav>
  );
}
