/**
 * axe-core WCAG 2.1 AA scan for /me/history (ISSUE-065, NFR-012).
 *
 * We scan the populated list state because it carries the highest
 * structural complexity — empty + error states reuse the same shell
 * and are covered functionally in page.test.tsx.
 *
 * `color-contrast` is disabled because jsdom doesn't compute real CSS;
 * the design system already passes contrast at the token level.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
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

import { HistoryListView } from "@/app/me/history/HistoryListView";

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

const ROWS = [
  {
    id: "r-1",
    category: "love",
    started_at: "2026-05-25T09:30:00+00:00",
    completed_at: "2026-05-25T09:31:30+00:00",
    audio_available: true,
    summary: "그 사람은 너랑 코드가 안 맞아.",
  },
  {
    id: "r-2",
    category: "work",
    started_at: "2026-05-20T11:00:00+00:00",
    completed_at: "2026-05-20T11:01:30+00:00",
    audio_available: false,
    summary: "이직? 1년만 더 버텨봐.",
  },
];

describe("/me/history a11y", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("loaded state has no axe-core violations", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkOkResponse(ROWS));

    const { container, getByTestId } = render(
      <HistoryListView fetchImpl={fetchImpl} />,
    );

    await waitFor(() => {
      expect(getByTestId("me-history-list-loaded")).toBeInTheDocument();
    });

    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it("empty state has no axe-core violations", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(mkOkResponse([]));

    const { container, getByTestId } = render(
      <HistoryListView fetchImpl={fetchImpl} />,
    );

    await waitFor(() => {
      expect(getByTestId("me-history-list-empty")).toBeInTheDocument();
    });

    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
