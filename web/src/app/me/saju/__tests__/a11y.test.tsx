/**
 * axe-core WCAG 2.1 AA scan for /me/saju (ISSUE-064, NFR-013).
 *
 * Scans the loaded chart state — the canonical render. Loading/error
 * states reuse the same chrome and are covered structurally in
 * page.test.tsx.
 *
 * `color-contrast` is disabled because jsdom doesn't compute real CSS
 * (the design system already passes contrast at the token level).
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor, act } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

import MeSajuPage from "@/app/me/saju/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

function mkOkResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
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
};

describe("/me/saju — WCAG 2.1 AA", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => mkOkResponse(CHART_BODY)),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("has zero axe violations on the loaded chart state", async () => {
    let container: HTMLElement | undefined;
    await act(async () => {
      ({ container } = render(<MeSajuPage />));
    });
    await waitFor(() => {
      expect(
        container!.querySelector('[data-testid="me-saju-loaded"]'),
      ).not.toBeNull();
    });
    const results = await axe(container!, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
