/**
 * ISSUE-096 — RouteShell variant resolver.
 *
 * Pure pathname → variant table for the per-screen v2 nav chrome.
 *
 *   /                  → "landing"        brand-mark + back affordance only
 *   /reading/category  → "vertical"       .nav-vertical (writing-mode: vertical-rl)
 *   /reading/play      → "bottom-v2"      .nav-bottom-v2 (sticky bottom, immersive)
 *   /me, /me/saju, …   → "hanja-tab"      4-button hanja tab bar (家 命 月 我)
 *   everything else    → "default"        fallback (consumer decides legacy chrome)
 *
 * The function takes a normalised pathname (no trailing slash, no query) and
 * never touches React APIs — so it's trivially unit-testable. `RouteShell`
 * wires it to `usePathname()`.
 */
export type NavVariant = 'landing' | 'vertical' | 'bottom-v2' | 'hanja-tab' | 'default';

const HANJA_TAB_PREFIX = '/me'; // /me, /me/saju, /me/profile, /me/history, …

/**
 * Resolve the nav variant for a route.
 *
 * Matching strategy:
 *   1. Exact `/` → landing.
 *   2. Exact `/reading/category` → vertical.
 *   3. `/reading/play` (with or without nested subroute) → bottom-v2.
 *   4. `/me` or anything starting with `/me/` → hanja-tab.
 *   5. otherwise → default.
 *
 * The category nav is intentionally exact-only because we don't want
 * `/reading/category/foo` (none exists today, but future detail screens
 * may) to inherit the vertical chrome silently.
 */
export function resolveNavVariant(pathname: string): NavVariant {
  // Normalise — strip trailing slash unless the path IS the root.
  const p = pathname.length > 1 && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;

  if (p === '/') return 'landing';
  if (p === '/reading/category') return 'vertical';
  if (p === '/reading/play' || p.startsWith('/reading/play/')) {
    return 'bottom-v2';
  }
  if (p === HANJA_TAB_PREFIX || p.startsWith(`${HANJA_TAB_PREFIX}/`)) {
    return 'hanja-tab';
  }
  return 'default';
}

/**
 * Hanja tab specification — single source of truth for the My Page tab bar.
 *
 * Order locked by docs/wireframes.md §11 Tab bar (홈 · 사주 · 타로 · 마이).
 * Hanja chars come from docs/design_system.md §"Hanja Monument" character set,
 * mapped so each tab carries its own meaning while still announcing the
 * Korean label to screen readers.
 *
 * Routes intentionally do NOT redirect users to a non-existent screen — the
 * 我 ("마이") tab points to /me/profile in the spec, but our codebase currently
 * exposes /me as the profile root. The fallback `/me` is used so the tab is
 * always reachable; ISSUE-098 / future profile screens can split this later.
 */
export interface HanjaTab {
  /** Stable id (for keying + active comparison). */
  key: 'home' | 'saju' | 'tarot' | 'me';
  /** Hanja character rendered as the tab visual. */
  hanja: string;
  /** Spoken Korean label — screen readers announce this, not the hanja. */
  ariaLabel: string;
  /** Target href. */
  href: string;
}

export const HANJA_TABS: ReadonlyArray<HanjaTab> = [
  { key: 'home', hanja: '家', ariaLabel: '홈', href: '/me' },
  { key: 'saju', hanja: '命', ariaLabel: '사주', href: '/me/saju' },
  { key: 'tarot', hanja: '月', ariaLabel: '타로', href: '/tarot' },
  // The issue brief says /me/profile but that page does not yet exist; the
  // closest production-shipped equivalent is /me/account (logout/account
  // settings) and the issue Notes explicitly say "allow override via prop
  // for special cases". We default to /me/account so the link is real today;
  // a future profile screen issue can swap the href without rev-locking
  // this component.
  { key: 'me', hanja: '我', ariaLabel: '마이', href: '/me/account' },
];

/**
 * Compute the active hanja-tab key for a given pathname.
 *
 * Exact + longest-prefix match. `/me` is the root, so we have to be careful
 * to only treat exact `/me` (or `/me?…`) as "home" — every other `/me/...`
 * must fall through to a non-home tab so the underline lands where the user
 * actually is.
 */
export function activeHanjaTabKey(pathname: string): HanjaTab['key'] | undefined {
  const p = pathname.length > 1 && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;

  if (p === '/me') return 'home';
  if (p.startsWith('/me/saju')) return 'saju';
  if (p.startsWith('/tarot')) return 'tarot';
  if (p.startsWith('/me/account')) return 'me';
  // Any other /me/* path leaves no underline rather than mis-assigning it.
  return undefined;
}
