/**
 * Stubbed `/api/v1/me` fetcher (ISSUE-030).
 *
 * The real endpoint lands in ISSUE-040 (entitlement check service). For now we
 * return a typed mock so the category screen can render every documented state
 * (non-member / free_token / single payment required / subscriber). The variant
 * is selected via the `?entitlement=<kind>` query param — dev only, no auth
 * coupling. In production the param is ignored and we fall back to the
 * "non-member" default until ISSUE-040 ships the real call.
 *
 * Contract mirrors architecture.md §6.1:
 *   GET /api/v1/me → { user_id, profile?, runtime_caps, has_subscription,
 *                       has_free_token }
 *
 * We narrow that to the fields the category screen actually consumes — the
 * entitlement kind + the subscriber's monthly_remaining counter (sourced from
 * the bottom-bar requirement in ux_spec Screen 6 success/edge state).
 */

export type EntitlementKind =
  | "none"
  | "free_token"
  | "payment"
  | "subscription";

export interface MeStubResponse {
  entitlement_kind: EntitlementKind;
  /**
   * Non-member signup grant remaining. The spec wires this to the bottom-bar
   * copy "무료 토큰 1회"; in the stub it's a constant 1.
   */
  signup_grant_remaining: number;
  /**
   * Subscriber's monthly saju credit remaining (1 if unused, 0 if consumed
   * this billing cycle). Only meaningful when entitlement_kind === "subscription".
   */
  monthly_remaining: number;
}

/**
 * Permitted override values for the `?entitlement=...` query param. Anything
 * outside this set falls through to the default response.
 */
const VALID_OVERRIDES: ReadonlySet<EntitlementKind> = new Set<EntitlementKind>([
  "none",
  "free_token",
  "payment",
  "subscription",
]);

/**
 * Build the stubbed response. Pure function — accepts the override directly so
 * unit tests don't need to mock `useSearchParams()`. Production callers pass
 * `null` (or omit) and get the default non-member shape.
 */
export function buildMeStub(override?: string | null): MeStubResponse {
  if (override && VALID_OVERRIDES.has(override as EntitlementKind)) {
    const kind = override as EntitlementKind;
    return {
      entitlement_kind: kind,
      signup_grant_remaining: kind === "free_token" ? 1 : 0,
      // Subscriber state: assume unused this cycle in the stub.
      monthly_remaining: kind === "subscription" ? 1 : 0,
    };
  }
  // Default: non-member, no entitlement yet. Matches the canonical first-visit
  // state in Flow A step 6 (the user has just completed onboarding and is about
  // to consume their signup grant on the subsequent paywall).
  return {
    entitlement_kind: "none",
    signup_grant_remaining: 0,
    monthly_remaining: 0,
  };
}
