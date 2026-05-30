/**
 * Unit tests for `/tarot` page (ISSUE-050, Screen 12).
 *
 * AC coverage delegated to this file:
 * - AC3 — when `requires_payment=true` (quota=0, non-subscriber) and
 *   the user taps the card, the page calls `router.push('/tarot/paywall')`
 *   WITHOUT triggering a flip.
 * - AC5 — when `state='face_up'` (already-flipped same-day return), the
 *   page renders the "다시 듣기" CTA wired to `/tarot/play`.
 *
 * AC1, AC2, AC4 are covered at the component level (TarotCard +
 * TarotQuotaBanner tests) — the page just plumbs props.
 *
 * Why we mock fetch + next/navigation:
 * - jsdom has no real fetch and no Next router. We provide thin mocks
 *   so the page can be rendered in isolation.
 * - We keep the page test SMALL per the ISSUE-042 OOM lesson: only two
 *   tests, each with its own render(), and `cleanup()` in afterEach.
 *   No fake timers, no repeated rerender cycles.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: pushMock }),
  useSearchParams: () => new URLSearchParams(),
}));

import TarotPage from "@/app/tarot/page";

interface TodayBody {
  card_index: number;
  card_name: string;
  card_art_url: string;
  free_remaining: number;
  requires_payment: boolean;
  // The architecture §6.4 contract leaves room for an already-flipped
  // marker; the page reads it to surface the "다시 듣기" CTA per AC5.
  already_flipped?: boolean;
}

function mockFetchOnce(body: TodayBody, status = 200) {
  globalThis.fetch = vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  ) as unknown as typeof fetch;
}

afterEach(() => {
  cleanup();
  pushMock.mockReset();
});

beforeEach(() => {
  pushMock.mockReset();
});

describe("/tarot page — Screen 12", () => {
  it("AC3 — quota=0 + tap routes to /tarot/paywall (no flip)", async () => {
    mockFetchOnce({
      card_index: 3,
      card_name: "여황제",
      card_art_url: "/api/v1/tarot/cards/3/art",
      free_remaining: 0,
      requires_payment: true,
    });

    await act(async () => {
      render(<TarotPage />);
    });

    // The card is rendered face-down (the quota guard happens on tap,
    // not on mount — matches the ux_spec "optimistic render" note).
    const card = await screen.findByRole("button", { name: /오늘의 카드/ });
    expect(card).toHaveAttribute("data-state", "face_down");

    await act(async () => {
      fireEvent.click(card);
    });

    expect(pushMock).toHaveBeenCalledWith("/tarot/paywall");
    // No flip happened: the surface stays face_down.
    expect(card).toHaveAttribute("data-state", "face_down");
  });

  it("AC5 — already-flipped server state renders the 다시 듣기 CTA", async () => {
    mockFetchOnce({
      card_index: 17,
      card_name: "달",
      card_art_url: "/api/v1/tarot/cards/17/art",
      free_remaining: 0,
      requires_payment: false,
      already_flipped: true,
    });

    await act(async () => {
      render(<TarotPage />);
    });

    // Face-up surface (revealed art + CTA).
    expect(await screen.findByAltText("달")).toBeInTheDocument();
    const replay = await screen.findByRole("button", { name: "다시 듣기" });
    expect(replay).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(replay);
    });
    expect(pushMock).toHaveBeenCalledWith("/tarot/play");
  });
});
