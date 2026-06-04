/**
 * v2 (Ink, Amber & 印) feature flags — ISSUE-094 (and forward-compat
 * for ISSUE-095/096/097/098).
 *
 * Why a tiny module instead of inlining `process.env.NEXT_PUBLIC_*`:
 * - Centralises the truthy parsing so "true" / "1" / "TRUE" all behave
 *   identically, and unrelated values fall through to false.
 * - Gives tests a stable import surface — they mutate `process.env`
 *   directly, then call the accessor, and don't need to re-mock Next
 *   internals.
 * - Lets the page/component code stay declarative: a boolean import
 *   replaces a stringly-typed env lookup with branching.
 *
 * Read-on-call semantics (not cached at module load) so the test suite
 * can flip the flag between test cases. In production the env var is
 * baked at build time by Next so the runtime overhead is negligible.
 */

function parseBoolFlag(raw: string | undefined): boolean {
  if (!raw) return false;
  const v = raw.trim().toLowerCase();
  return v === 'true' || v === '1';
}

export function isTarotV2SpreadEnabled(): boolean {
  return parseBoolFlag(process.env.NEXT_PUBLIC_TAROT_V2_SPREAD);
}

/**
 * `NEXT_PUBLIC_QUOTE_CARD_V2` — ISSUE-095 rollout gate.
 *
 * When true: `<QuoteCardPreview v="v2">` renders client-side AND the
 * edge route serves the v2 OG layout. When false (default): the v1
 * Pillow-baked / `@vercel/og` JSX from ISSUE-058/060 is served.
 */
export function isQuoteCardV2Enabled(): boolean {
  return parseBoolFlag(process.env.NEXT_PUBLIC_QUOTE_CARD_V2);
}

/**
 * `NEXT_PUBLIC_NAV_V2` — ISSUE-096 rollout gate.
 *
 * When true: `<RouteShell>` mounts the per-screen v2 chrome
 * (landing minimal · `.nav-vertical` on category · `.nav-bottom-v2`
 * on reading-play · hanja tab bar on /me).
 *
 * When false / unset (default): `<RouteShell>` renders the v1
 * TopAppBar/BottomTabBar pair on every screen so production stays on
 * the ISSUE-022 chrome until launch readiness flips this. The rollback
 * path documented in the issue body (NAV_V2=false) is identical to
 * "env var unset" — both paths short-circuit before any v2 CSS class
 * lands in the DOM.
 */
export function isNavV2Enabled(): boolean {
  return parseBoolFlag(process.env.NEXT_PUBLIC_NAV_V2);
}
