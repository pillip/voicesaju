/**
 * Unit tests for `/me/history` (ISSUE-065, Screen 18).
 *
 * AC mapping (issues.md §ISSUE-065):
 *   AC1: 5 past readings → 5 rows in the order returned by the
 *        backend (already desc by `started_at`).
 *   AC2: 0 readings → empty state with 누님 illustration placeholder
 *        + "아직 풀이가 없네. 첫 풀이 받아볼래?" + CTA → /reading/category.
 *   AC3: expired audio row → "재생 불가" pill + aria-disabled + no link.
 *   AC4: tap an available row → navigate to /me/history/[id].
 *
 * Strategy:
 *   - Render `HistoryListView` directly so we can inject a fake
 *     `fetchImpl` and skip the `page.tsx` Promise wrapper.
 *   - Mock `next/navigation` so we can observe `router.replace` for
 *     the 401 redirect path (covered as a separate test).
 *   - `next/link` resolves to a passthrough <a> under jsdom (set up
 *     globally in vitest.setup), so assertions on `href` and `tagName`
 *     are stable.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

import { HistoryListView } from "@/app/me/history/HistoryListView";

function mkOkResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function mkErrResponse(status: number): Response {
  return {
    ok: false,
    status,
    json: async () => ({}),
  } as unknown as Response;
}

// Five rows pre-sorted desc by started_at — mirrors the backend's
// ORDER BY clause so the test asserts the page renders rows as
// received without re-sorting.
const FIVE_ROWS = [
  {
    id: "r-5",
    category: "love",
    started_at: "2026-05-25T09:30:00+00:00",
    completed_at: "2026-05-25T09:31:30+00:00",
    audio_available: true,
    summary: "그 사람은 너랑 코드가 안 맞아.",
  },
  {
    id: "r-4",
    category: "work",
    started_at: "2026-05-20T11:00:00+00:00",
    completed_at: "2026-05-20T11:01:30+00:00",
    audio_available: true,
    summary: "이직? 1년만 더 버텨봐.",
  },
  {
    id: "r-3",
    category: "money",
    started_at: "2026-05-15T08:00:00+00:00",
    completed_at: "2026-05-15T08:01:30+00:00",
    audio_available: true,
    summary: "큰 돈은 안 들어와. 그래도 잘 버틸 거야.",
  },
  {
    id: "r-2",
    category: "tarot",
    started_at: "2026-05-10T07:00:00+00:00",
    completed_at: "2026-05-10T07:01:30+00:00",
    audio_available: true,
    summary: "오늘은 숨겨진 진실이 보이는 날.",
  },
  {
    id: "r-1",
    category: "love",
    started_at: "2026-05-05T07:00:00+00:00",
    completed_at: "2026-05-05T07:01:30+00:00",
    audio_available: true,
    summary: "결혼은 아직 일러.",
  },
] as const;

const EXPIRED_ROW = {
  id: "r-old",
  category: "love",
  started_at: "2025-12-01T07:00:00+00:00",
  completed_at: "2025-12-01T07:01:30+00:00",
  audio_available: false,
  summary: "예전 풀이.",
} as const;

describe("HistoryListView (/me/history)", () => {
  beforeEach(() => {
    replaceMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("AC1: 5 readings → 5 rows in desc order", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkOkResponse(FIVE_ROWS));

    render(<HistoryListView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-history-list-loaded")).toBeInTheDocument();
    });
    const list = screen.getByTestId("me-history-list");
    const items = list.querySelectorAll("li");
    expect(items.length).toBe(5);

    // Verify the order matches the input array (desc as returned).
    // Each row's wrapper has data-testid="me-history-row-<id>".
    const renderedIds = Array.from(items).map((li) => {
      const wrapper = li.querySelector('[data-testid^="me-history-row-"]');
      const id = wrapper?.getAttribute("data-testid") ?? "";
      return id.replace(/^me-history-row-/, "");
    });
    expect(renderedIds).toEqual(["r-5", "r-4", "r-3", "r-2", "r-1"]);

    // Date cell on the first row is the YYYY-MM-DD slice of started_at.
    expect(screen.getByTestId("me-history-row-date-r-5").textContent).toBe(
      "2026-05-25",
    );
    // Category badge on the first row maps love → 연애.
    expect(screen.getByTestId("me-history-row-category-r-5").textContent).toBe(
      "연애",
    );
  });

  it("AC2: 0 readings → empty state + illustration placeholder + CTA → /reading/category", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkOkResponse([]));

    render(<HistoryListView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-history-list-empty")).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("me-history-list-empty-illustration"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("아직 풀이가 없네. 첫 풀이 받아볼래?"),
    ).toBeInTheDocument();
    const cta = screen.getByTestId("me-history-list-empty-cta");
    expect(cta).toBeInTheDocument();
    expect(cta.getAttribute("href")).toBe("/reading/category");
  });

  it('AC3: expired audio row → "재생 불가" pill + aria-disabled + no link', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkOkResponse([EXPIRED_ROW]));

    render(<HistoryListView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-history-list-loaded")).toBeInTheDocument();
    });
    const row = screen.getByTestId(`me-history-row-${EXPIRED_ROW.id}`);
    // Expired rows render as <div>, not <a>. Asserting on tagName
    // catches a regression where the link wrapper gets rendered with
    // an aria-disabled marker but still has a clickable href.
    expect(row.tagName.toLowerCase()).toBe("div");
    expect(row.getAttribute("aria-disabled")).toBe("true");
    expect(
      screen.getByTestId(`me-history-row-disabled-pill-${EXPIRED_ROW.id}`),
    ).toHaveTextContent("재생 불가");
    // No play icon next to expired rows.
    expect(
      screen.queryByTestId(`me-history-row-play-${EXPIRED_ROW.id}`),
    ).toBeNull();
  });

  it("AC4: tap an available row → href targets /me/history/[id] with date query", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkOkResponse([FIVE_ROWS[0]]));

    render(<HistoryListView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-history-list-loaded")).toBeInTheDocument();
    });
    const row = screen.getByTestId(`me-history-row-${FIVE_ROWS[0].id}`);
    expect(row.tagName.toLowerCase()).toBe("a");
    expect(row.getAttribute("href")).toBe("/me/history/r-5?d=2026-05-25");
  });

  it("renders the loading shell before the fetch resolves", () => {
    const fetchImpl = vi
      .fn()
      .mockReturnValue(new Promise<Response>(() => undefined));

    render(<HistoryListView fetchImpl={fetchImpl} />);

    expect(screen.getByTestId("me-history-list-loading")).toBeInTheDocument();
    expect(
      screen.getByTestId("me-history-list-loading").getAttribute("aria-busy"),
    ).not.toBeNull();
  });

  it("renders an error shell + retry button when the fetch returns 500", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(mkErrResponse(500))
      .mockResolvedValueOnce(mkOkResponse(FIVE_ROWS));

    render(<HistoryListView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-history-list-error")).toBeInTheDocument();
    });
    const retry = screen.getByTestId("me-history-list-retry");
    expect(retry).toBeInTheDocument();
    // Tap retry → page reloads + transitions to loaded.
    retry.click();
    await waitFor(() => {
      expect(screen.getByTestId("me-history-list-loaded")).toBeInTheDocument();
    });
  });

  it("redirects to /auth/login on a 401 response", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkErrResponse(401));

    render(<HistoryListView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/auth/login");
    });
  });
});
