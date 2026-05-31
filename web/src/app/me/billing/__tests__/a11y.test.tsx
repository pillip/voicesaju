/**
 * axe-core WCAG 2.1 AA scan for /me/billing (ISSUE-067, NFR-012).
 *
 * Scans both states (subscriber + non-subscriber empty) since the
 * page renders structurally different markup in each.
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

import { BillingView } from "@/app/me/billing/BillingView";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

function mkOkResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

const ACTIVE_SUB = {
  id: "sub-1",
  status: "active",
  monthly_saju_remaining: 1,
  current_period_start: "2026-05-01T00:00:00+00:00",
  current_period_end: "2026-05-31T00:00:00+00:00",
  cancel_requested_at: null,
};

const PAYMENT_ROW = {
  id: "pmt-1",
  type: "single",
  category: null,
  amount_krw: 5900,
  status: "paid",
  paid_at: "2026-05-01T00:00:00+00:00",
  refunded_amount_krw: 0,
};

function makeFetch(subBody: unknown, pmtBody: unknown) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const urlStr = typeof url === "string" ? url : url.toString();
    if (urlStr.startsWith("/api/v1/subscriptions/me")) {
      return mkOkResponse(subBody);
    }
    if (urlStr.startsWith("/api/v1/payments/history")) {
      return mkOkResponse(pmtBody);
    }
    throw new Error(`unmocked URL: ${urlStr}`);
  });
}

describe("/me/billing a11y", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("subscriber state has no axe-core violations", async () => {
    const fetchImpl = makeFetch({ subscription: ACTIVE_SUB }, [PAYMENT_ROW]);

    const { container, getByTestId } = render(
      <BillingView fetchImpl={fetchImpl} />,
    );

    await waitFor(() => {
      expect(getByTestId("me-billing-loaded")).toBeInTheDocument();
    });

    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it("non-subscriber empty state has no axe-core violations", async () => {
    const fetchImpl = makeFetch({ subscription: null }, []);

    const { container, getByTestId } = render(
      <BillingView fetchImpl={fetchImpl} />,
    );

    await waitFor(() => {
      expect(getByTestId("me-billing-loaded")).toBeInTheDocument();
    });

    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
