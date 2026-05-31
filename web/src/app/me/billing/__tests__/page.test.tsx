/**
 * Unit tests for `/me/billing` (ISSUE-067, Screen 20).
 *
 * AC mapping (issues.md §ISSUE-067):
 *   AC1: subscriber → tier (월 구독 · 9,900원) + next billing date +
 *        "구독 해지" button visible.
 *   AC2: non-subscriber + no purchases → empty state + "구독 시작하기"
 *        CTA targeting /me/billing/subscribe.
 *   AC3: tap 구독 해지 → ConfirmModal with next billing date in body.
 *   AC4: confirm cancel → success → "해지 예정 — [date]까지 이용 가능"
 *        pill replaces the cancel button.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react";

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

import { BillingView } from "@/app/me/billing/BillingView";

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

const ACTIVE_SUB = {
  id: "sub-1",
  status: "active",
  monthly_saju_remaining: 1,
  current_period_start: "2026-05-01T00:00:00+00:00",
  current_period_end: "2026-05-31T00:00:00+00:00",
  cancel_requested_at: null,
};

const CANCEL_PENDING_SUB = {
  ...ACTIVE_SUB,
  status: "cancel_at_period_end",
  cancel_requested_at: "2026-05-15T00:00:00+00:00",
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

/**
 * Helper: drive the parallel fetch on mount.
 *
 * The page issues GETs to /subscriptions/me and /payments/history in
 * parallel. The fake fetch routes on URL so we don't depend on call
 * order. Additional calls (e.g. cancel POST) get their own handler.
 */
function makeFetch(
  subBody: unknown,
  pmtBody: unknown,
  opts: {
    subStatus?: number;
    pmtStatus?: number;
    cancelBody?: unknown;
    cancelStatus?: number;
  } = {},
) {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const urlStr = typeof url === "string" ? url : url.toString();
    if (urlStr.startsWith("/api/v1/subscriptions/me")) {
      return mkOkResponse(subBody, opts.subStatus ?? 200);
    }
    if (urlStr.startsWith("/api/v1/payments/history")) {
      return mkOkResponse(pmtBody, opts.pmtStatus ?? 200);
    }
    if (urlStr.startsWith("/api/v1/subscriptions/cancel")) {
      if (init?.method !== "POST") {
        throw new Error(`expected POST for cancel, got ${init?.method}`);
      }
      return mkOkResponse(
        opts.cancelBody ?? CANCEL_PENDING_SUB,
        opts.cancelStatus ?? 200,
      );
    }
    throw new Error(`unmocked URL: ${urlStr}`);
  });
}

describe("BillingView (/me/billing)", () => {
  beforeEach(() => {
    replaceMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("AC1: subscriber → tier + next billing + 구독 해지 button", async () => {
    const fetchImpl = makeFetch({ subscription: ACTIVE_SUB }, [PAYMENT_ROW]);

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-loaded")).toBeInTheDocument();
    });
    expect(screen.getByTestId("me-billing-plan-tier").textContent).toContain(
      "월 구독",
    );
    expect(screen.getByTestId("me-billing-plan-tier").textContent).toContain(
      "9,900원",
    );
    expect(screen.getByTestId("me-billing-next-billing").textContent).toContain(
      "2026-05-31",
    );
    expect(screen.getByTestId("me-billing-cancel-button")).toBeInTheDocument();
    // History list rendered with the single payment row.
    expect(screen.getByTestId("me-billing-history-list")).toBeInTheDocument();
    expect(
      screen.getByTestId(`me-billing-history-row-${PAYMENT_ROW.id}`),
    ).toBeInTheDocument();
  });

  it("AC2: non-subscriber + no payments → empty state + 구독 시작하기 CTA", async () => {
    const fetchImpl = makeFetch({ subscription: null }, []);

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-loaded")).toBeInTheDocument();
    });
    expect(screen.getByTestId("me-billing-plan-tier").textContent).toBe("무료");
    const cta = screen.getByTestId("me-billing-start-cta");
    expect(cta).toBeInTheDocument();
    expect(cta.getAttribute("href")).toBe("/me/billing/subscribe");
    // Empty payment-history surface.
    expect(screen.getByTestId("me-billing-history-empty")).toHaveTextContent(
      "결제 내역이 없어요",
    );
    // Cancel button must NOT be present for non-subscribers.
    expect(screen.queryByTestId("me-billing-cancel-button")).toBeNull();
  });

  it("AC3: tap 구독 해지 → ConfirmModal with next billing date in body", async () => {
    const fetchImpl = makeFetch({ subscription: ACTIVE_SUB }, []);

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-loaded")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("me-billing-cancel-button"));

    // ConfirmModal renders the title + description in the DOM.
    expect(screen.getByText("정말 해지할 거야?")).toBeInTheDocument();
    // Body must include the next-billing date (AC3 explicit requirement).
    expect(
      screen.getByText(/2026-05-31까지는 그대로 쓸 수 있어/),
    ).toBeInTheDocument();
  });

  it('AC4: confirm cancel → "해지 예정 — [date]까지 이용 가능" pill', async () => {
    const fetchImpl = makeFetch({ subscription: ACTIVE_SUB }, []);

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-loaded")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("me-billing-cancel-button"));
    // ConfirmModal exposes the confirm button via the "그래도 해지" label.
    const confirmBtn = screen.getByRole("button", { name: "그래도 해지" });

    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("me-billing-cancel-pending-pill"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("me-billing-cancel-pending-pill").textContent,
    ).toContain("해지 예정 — 2026-05-31까지 이용 가능");
    // Cancel button must be hidden once the pending state is rendered.
    expect(screen.queryByTestId("me-billing-cancel-button")).toBeNull();
  });

  it("renders the loading shell before the parallel fetches resolve", () => {
    const pending = vi.fn(() => new Promise<Response>(() => undefined));
    render(<BillingView fetchImpl={pending} />);
    expect(screen.getByTestId("me-billing-loading")).toBeInTheDocument();
  });

  it("renders the error shell + retry when the subscription fetch fails", async () => {
    let firstCall = true;
    const fetchImpl = vi.fn(async (url: RequestInfo | URL) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      if (urlStr.startsWith("/api/v1/subscriptions/me")) {
        if (firstCall) {
          firstCall = false;
          return mkErrResponse(500);
        }
        return mkOkResponse({ subscription: null });
      }
      return mkOkResponse([]);
    });

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-error")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("me-billing-retry"));

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-loaded")).toBeInTheDocument();
    });
  });

  it("redirects to /auth/login on a 401 from /subscriptions/me", async () => {
    const fetchImpl = makeFetch({ subscription: null }, [], { subStatus: 401 });

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/auth/login");
    });
  });

  it("renders the cancel-pending pill on initial load if already cancel_at_period_end", async () => {
    const fetchImpl = makeFetch({ subscription: CANCEL_PENDING_SUB }, [
      PAYMENT_ROW,
    ]);

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(
        screen.getByTestId("me-billing-cancel-pending-pill"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId("me-billing-cancel-button")).toBeNull();
    expect(screen.queryByTestId("me-billing-next-billing")).toBeNull();
  });

  it("shows cancel error toast when the POST returns 401", async () => {
    const fetchImpl = makeFetch({ subscription: ACTIVE_SUB }, [], {
      cancelStatus: 401,
    });

    render(<BillingView fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-loaded")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("me-billing-cancel-button"));
    const confirmBtn = screen.getByRole("button", { name: "그래도 해지" });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(screen.getByTestId("me-billing-cancel-error")).toBeInTheDocument();
    });
    // Cancel button still visible — the API failed so the row state didn't change.
    expect(screen.getByTestId("me-billing-cancel-button")).toBeInTheDocument();
  });
});
