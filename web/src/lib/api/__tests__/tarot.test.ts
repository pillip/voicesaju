/**
 * Unit tests for the daily-tarot HTTP client (ISSUE-050).
 *
 * The client wraps `GET /api/v1/tarot/today` — the only endpoint the
 * Screen 12 page reads on mount. Flip + SSE (ISSUE-051) live elsewhere.
 *
 * AC mapping:
 * - AC1 (quota=1) — happy-path JSON parses into `TarotTodayResponse`.
 * - AC3 (quota=0) — `requires_payment=true` flag round-trips so the page
 *   can branch into the paywall redirect.
 * - Error envelope — non-2xx responses surface as `TarotApiError`
 *   carrying the HTTP status, so the page can decide whether to retry,
 *   show a toast, or treat as an empty state.
 */
import { describe, expect, it, vi } from "vitest";
import { fetchTarotToday, TarotApiError } from "@/lib/api/tarot";

describe("fetchTarotToday", () => {
  it("parses the happy-path quota=1 envelope", async () => {
    const fakeFetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            card_index: 17,
            card_name: "달",
            card_art_url: "/api/v1/tarot/cards/17/art",
            free_remaining: 1,
            requires_payment: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );

    const out = await fetchTarotToday(fakeFetch as unknown as typeof fetch);
    expect(out.card_index).toBe(17);
    expect(out.card_name).toBe("달");
    expect(out.card_art_url).toBe("/api/v1/tarot/cards/17/art");
    expect(out.free_remaining).toBe(1);
    expect(out.requires_payment).toBe(false);
    expect(fakeFetch).toHaveBeenCalledWith(
      "/api/v1/tarot/today",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("parses the quota=0 / requires_payment envelope", async () => {
    const fakeFetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            card_index: 3,
            card_name: "여황제",
            card_art_url: "/api/v1/tarot/cards/3/art",
            free_remaining: 0,
            requires_payment: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );

    const out = await fetchTarotToday(fakeFetch as unknown as typeof fetch);
    expect(out.free_remaining).toBe(0);
    expect(out.requires_payment).toBe(true);
  });

  it("throws TarotApiError when the server returns a non-2xx", async () => {
    const fakeFetch = vi.fn(
      async () => new Response('{"detail":"unauthorized"}', { status: 401 }),
    );

    await expect(
      fetchTarotToday(fakeFetch as unknown as typeof fetch),
    ).rejects.toBeInstanceOf(TarotApiError);
    await expect(
      fetchTarotToday(fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({
      status: 401,
    });
  });

  it("wraps network failures as TarotApiError with status=null", async () => {
    const fakeFetch = vi.fn(async () => {
      throw new Error("boom");
    });

    await expect(
      fetchTarotToday(fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({
      status: null,
    });
  });
});
