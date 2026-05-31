/**
 * Unit tests for `/error/llm-failed` (ISSUE-075, Screen 26, FR-033).
 *
 * AC mapping:
 *   - Renders the Screen 26 layout: 누님 placeholder + "별기운이 잠시
 *     약하네…" H1 + body + 다시 시도/마이페이지로 CTAs.
 *   - 다시 시도 → `router.push('/reading/category')`.
 *   - 마이페이지로 → `router.push('/me')`.
 *   - Zero axe-core violations (NFR-012).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// eslint-disable-next-line import/first
import LlmFailedPage from "@/app/error/llm-failed/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

describe("/error/llm-failed (Screen 26)", () => {
  beforeEach(() => {
    pushMock.mockReset();
  });

  it("renders the Screen 26 layout", () => {
    render(<LlmFailedPage />);
    expect(screen.getByTestId("llm-failed")).toBeTruthy();
    expect(screen.getByTestId("llm-failed-persona")).toBeTruthy();
    // The H1 includes a horizontal ellipsis (U+2026), not three dots.
    expect(screen.getByTestId("llm-failed-title").textContent).toContain(
      "별기운이 잠시 약하네",
    );
    expect(screen.getByTestId("llm-failed-body").textContent).toContain(
      "환불 또는 무료 이용권",
    );
  });

  it('"다시 시도" CTA navigates to /reading/category', () => {
    render(<LlmFailedPage />);
    fireEvent.click(screen.getByTestId("llm-failed-retry"));
    expect(pushMock).toHaveBeenCalledWith("/reading/category");
  });

  it('"마이페이지로" CTA navigates to /me', () => {
    render(<LlmFailedPage />);
    fireEvent.click(screen.getByTestId("llm-failed-my"));
    expect(pushMock).toHaveBeenCalledWith("/me");
  });

  it("has zero axe violations", async () => {
    const { container } = render(<LlmFailedPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
