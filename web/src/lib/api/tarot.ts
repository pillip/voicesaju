/**
 * Daily-tarot HTTP client (ISSUE-050).
 *
 * Wraps `GET /api/v1/tarot/today` (ISSUE-049 backend). The Screen 12
 * page calls this on mount to pick up `{card_index, card_name,
 * card_art_url, free_remaining, requires_payment}` plus the optional
 * `already_flipped` marker that drives the AC5 "다시 듣기" CTA.
 *
 * `already_flipped` is sourced from the backend's `tarot_draws` row for
 * `(user, today_kst)`. Phase-1 the backend may or may not surface this
 * field — when absent we default to `false` and the page renders the
 * face-down hero. ISSUE-052 will guarantee the field by persisting the
 * draw on flip.
 *
 * `POST /api/v1/tarot/today/flip` lives in ISSUE-051 (the player) — not
 * here. This module stays narrow on purpose: one endpoint, one return
 * type, easy to mock in tests.
 */

export interface TarotTodayResponse {
  card_index: number;
  card_name: string;
  card_art_url: string;
  /** Weekly free draws left for non-subscribers. Subscribers get >= 1. */
  free_remaining: number;
  /** True iff the user has 0 quota AND no subscription bypass. */
  requires_payment: boolean;
  /**
   * Optional — true when the user already flipped today's card (same
   * KST date). The page surfaces the 다시 듣기 CTA when set.
   */
  already_flipped?: boolean;
}

export class TarotApiError extends Error {
  readonly status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "TarotApiError";
    this.status = status;
  }
}

export async function fetchTarotToday(
  fetchImpl: typeof fetch = fetch,
): Promise<TarotTodayResponse> {
  let res: Response;
  try {
    res = await fetchImpl("/api/v1/tarot/today", {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    throw new TarotApiError(
      `network error fetching /tarot/today: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }
  if (!res.ok) {
    throw new TarotApiError(
      `fetchTarotToday failed with status ${res.status}`,
      res.status,
    );
  }
  return (await res.json()) as TarotTodayResponse;
}
