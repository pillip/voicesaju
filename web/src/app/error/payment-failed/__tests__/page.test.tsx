/**
 * Unit tests for `/error/payment-failed` (ISSUE-075).
 *
 * AC mapping:
 *   - Renders the "결제가 안 됐네." H1 + retry/마이페이지로 CTAs.
 *   - 다시 시도 → `router.back()`.
 *   - 마이페이지로 → `router.push('/me')`.
 *   - Zero axe-core violations (NFR-012).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

const backMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    back: backMock,
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// eslint-disable-next-line import/first
import PaymentFailedPage from "@/app/error/payment-failed/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

describe("/error/payment-failed", () => {
  beforeEach(() => {
    backMock.mockReset();
    pushMock.mockReset();
  });

  it("renders the failure copy + both CTAs", () => {
    render(<PaymentFailedPage />);
    expect(screen.getByTestId("payment-failed")).toBeTruthy();
    expect(screen.getByText("결제가 안 됐네.")).toBeTruthy();
    expect(screen.getByTestId("payment-failed-retry")).toBeTruthy();
    expect(screen.getByTestId("payment-failed-my")).toBeTruthy();
  });

  it('"다시 시도" CTA calls router.back()', () => {
    render(<PaymentFailedPage />);
    fireEvent.click(screen.getByTestId("payment-failed-retry"));
    expect(backMock).toHaveBeenCalledTimes(1);
  });

  it('"마이페이지로" CTA navigates to /me', () => {
    render(<PaymentFailedPage />);
    fireEvent.click(screen.getByTestId("payment-failed-my"));
    expect(pushMock).toHaveBeenCalledWith("/me");
  });

  it("has zero axe violations", async () => {
    const { container } = render(<PaymentFailedPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
