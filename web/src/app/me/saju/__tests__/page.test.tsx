/**
 * Unit tests for `/me/saju` (ISSUE-064, Screen 17).
 *
 * AC mapping (issues.md §ISSUE-064):
 *   AC1: logged in + chart → 4 pillars render with KR labels.
 *   AC2: birth_time_known=false → Hour Pillar shows 모름, de-emphasized.
 *   AC3: tap cell → tooltip with 오행 + 십신.
 *   AC4: arrow-key nav moves tooltip focus across the grid.
 *   AC5: screen reader cell aria-label includes "년주 천간 무자, 오행 수, 십신 비견".
 *
 * Strategy mirrors `/me` (ISSUE-063):
 *   - Mock next/navigation so AC-equivalents (auth-bounce, no-profile-bounce)
 *     are observable via `router.replace`.
 *   - Stub global `fetch` per test to drive the state machine.
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

import MeSajuPage from "@/app/me/saju/page";

function mkOkResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
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

const CHART_BODY = {
  profile_id: "p-1",
  chart_id: "c-1",
  birth_time_known: true,
  chart: {
    year: { stem: "무", branch: "자", element: "수", ten_god: "편재" },
    month: { stem: "갑", branch: "오", element: "화", ten_god: "정관" },
    day: { stem: "경", branch: "신", element: "금", ten_god: "비견" },
    hour: { stem: "정", branch: "묘", element: "목", ten_god: "정인" },
    engine_version: "saju.v1.0",
  },
} as const;

const CHART_BODY_UNKNOWN_HOUR = {
  ...CHART_BODY,
  birth_time_known: false,
  chart: { ...CHART_BODY.chart, hour: null },
} as const;

describe("/me/saju (ISSUE-064)", () => {
  beforeEach(() => {
    replaceMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the loading skeleton then renders the chart on success (AC1)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mkOkResponse(CHART_BODY)),
    );
    render(<MeSajuPage />);
    // Initial render — loading.
    expect(screen.getByTestId("me-saju-loading")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("me-saju-loaded")).toBeInTheDocument();
    });
    // Column headers present (AC1).
    expect(screen.getByTestId("saju-full-chart-col-year").textContent).toBe(
      "년",
    );
    expect(screen.getByTestId("saju-full-chart-col-hour").textContent).toBe(
      "시",
    );
    // Edit link points to /me/edit-saju (route lands in ISSUE-071).
    const editLink = screen.getByTestId("me-saju-edit-link");
    expect(editLink.getAttribute("href")).toBe("/me/edit-saju");
    expect(editLink.textContent).toBe("정보 수정하기");
  });

  it("AC2: birth_time_known=false → 시 column shows 모름", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mkOkResponse(CHART_BODY_UNKNOWN_HOUR)),
    );
    render(<MeSajuPage />);
    await waitFor(() => {
      expect(screen.getByTestId("me-saju-loaded")).toBeInTheDocument();
    });
    expect(screen.getByTestId("saju-full-cell-천간-hour").textContent).toBe(
      "모름",
    );
    expect(
      screen.getByTestId("saju-full-chart-hour-unknown"),
    ).toBeInTheDocument();
  });

  it('401 → router.replace("/auth/login")', async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mkErrResponse(401)),
    );
    render(<MeSajuPage />);
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/auth/login");
    });
  });

  it('404 → router.replace("/onboarding")', async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mkErrResponse(404)),
    );
    render(<MeSajuPage />);
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/onboarding");
    });
  });

  it("5xx → error state with retry button", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mkErrResponse(500)),
    );
    render(<MeSajuPage />);
    await waitFor(() => {
      expect(screen.getByTestId("me-saju-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("me-saju-retry")).toBeInTheDocument();
  });

  it("network error → error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    render(<MeSajuPage />);
    await waitFor(() => {
      expect(screen.getByTestId("me-saju-error")).toBeInTheDocument();
    });
  });
});
