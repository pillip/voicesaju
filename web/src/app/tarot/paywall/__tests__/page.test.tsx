/**
 * Unit tests for `/tarot/paywall` page (ISSUE-050, Screen 24).
 *
 * Scope: this page is purely presentational at Phase-1 — it renders the
 * headline + two option cards and routes the user back via the back
 * arrow. The actual payment flow is wired in M5 (out of scope here).
 *
 * AC coverage:
 * - Page renders the Screen 24 headline + two payment option cards.
 * - axe-core scan is the a11y guardrail (no obvious WCAG violations).
 *
 * The option-tap → payment flow is NOT asserted because the M5 wiring
 * doesn't exist yet; the test would be vacuous.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { axe } from "jest-axe";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: pushMock, back: pushMock }),
  useSearchParams: () => new URLSearchParams(),
}));

import PaywallPage from "@/app/tarot/paywall/page";

afterEach(() => {
  cleanup();
  pushMock.mockReset();
});

describe("/tarot/paywall page — Screen 24", () => {
  it("renders the headline and two payment options", () => {
    render(<PaywallPage />);
    expect(
      screen.getByRole("heading", { name: "이번 주 무료 타로는 다 봤어" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /단건 결제/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /구독으로 매일 무제한/ }),
    ).toBeInTheDocument();
  });

  it("renders the footer copy explaining next-week reset", () => {
    render(<PaywallPage />);
    expect(
      screen.getByText("다음 주 월요일에 다시 무료 1회"),
    ).toBeInTheDocument();
  });

  it("has no axe-core a11y violations", async () => {
    const { container } = render(<PaywallPage />);
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
