/**
 * `/tarot` page — KST midnight banner wiring (ISSUE-053 / FR-013).
 *
 * AC coverage (page-level integration):
 *   - AC1: when the KST midnight callback fires, the page surfaces the
 *     "새로운 카드가 준비됐어요" banner AND calls `router.refresh()`.
 *
 * Why we mock `useKstMidnightRefresh` instead of using fake timers:
 *   The hook's own unit test
 *   (`src/lib/hooks/__tests__/useKstMidnightRefresh.test.ts`) already
 *   covers the timer arithmetic against KST with fake timers. At the
 *   page level we'd be exercising:
 *     (1) the same timer logic (redundant), AND
 *     (2) jsdom + fake timers + React mount fetch — a combo that's
 *         brittle (the mount fetch microtasks easily deadlock with the
 *         fake clock).
 *   Mocking the hook to immediately invoke the callback is sufficient
 *   to prove the page wires up the banner + refresh path, and it
 *   stays well within the ISSUE-042 OOM/test-stability budget.
 *
 * Test discipline:
 *   - Lives in a SEPARATE file from `page.test.tsx` so the existing
 *     two-test ISSUE-050 file stays minimal.
 *   - One render per `it`. Auto `cleanup()` runs via `vitest.setup.ts`.
 *   - The mock fetch returns a valid `today` payload so the page's
 *     mount effect doesn't error out.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

const refreshMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: pushMock,
    refresh: refreshMock,
  }),
  useSearchParams: () => new URLSearchParams(),
}));

// Capture the page's KST callback so the test can drive it manually.
let capturedMidnightCallback: (() => void) | null = null;

vi.mock("@/lib/hooks/useKstMidnightRefresh", () => ({
  useKstMidnightRefresh: (cb: () => void) => {
    capturedMidnightCallback = cb;
  },
}));

import TarotPage from "@/app/tarot/page";

interface TodayBody {
  card_index: number;
  card_name: string;
  card_art_url: string;
  free_remaining: number;
  requires_payment: boolean;
  already_flipped?: boolean;
  is_subscriber?: boolean;
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

beforeEach(() => {
  refreshMock.mockReset();
  pushMock.mockReset();
  capturedMidnightCallback = null;
});

afterEach(() => {
  capturedMidnightCallback = null;
});

describe("/tarot — KST midnight wiring (ISSUE-053)", () => {
  it("AC1 — midnight callback shows the banner and calls router.refresh()", async () => {
    mockFetchOnce({
      card_index: 9,
      card_name: "은둔자",
      card_art_url: "/api/v1/tarot/cards/9/art",
      free_remaining: 1,
      requires_payment: false,
    });

    await act(async () => {
      render(<TarotPage />);
    });

    // Pre-midnight: banner not yet visible, no refresh call.
    expect(
      screen.queryByTestId("tarot-kst-midnight-banner"),
    ).not.toBeInTheDocument();
    expect(refreshMock).not.toHaveBeenCalled();
    expect(capturedMidnightCallback).not.toBeNull();

    // Simulate the KST boundary crossing.
    await act(async () => {
      capturedMidnightCallback!();
    });

    // Banner is visible and the page asked the router for a refresh.
    expect(
      await screen.findByTestId("tarot-kst-midnight-banner"),
    ).toBeInTheDocument();
    expect(screen.getByText("새로운 카드가 준비됐어요")).toBeInTheDocument();
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });
});
