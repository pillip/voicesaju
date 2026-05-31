/**
 * Unit tests for `/legal/refund` (ISSUE-074, FR-036 AC3).
 *
 * AC mapping:
 *   - Renders title + back-to-home affordance.
 *   - Body documents the LLM-failure automatic refund path (FR-023 +
 *     FR-033 surface).
 *   - Body documents the failure-compensation 무료 이용권 fallback.
 *   - Zero axe-core violations (NFR-012).
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

import RefundPage from "@/app/legal/refund/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

describe("/legal/refund", () => {
  it("renders the title and back-to-home affordance", () => {
    render(<RefundPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "환불 정책" }),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "홈으로 돌아가기" })).toBeTruthy();
  });

  it("documents LLM-failure automatic refund (FR-036 AC3)", () => {
    const { container } = render(<RefundPage />);
    expect(container.textContent).toContain("LLM");
    expect(container.textContent).toContain("자동");
    expect(container.textContent).toMatch(/환불/);
  });

  it("documents failure-compensation 무료 이용권 fallback", () => {
    const { container } = render(<RefundPage />);
    expect(container.textContent).toContain("무료 이용권");
  });

  it("has zero axe violations", async () => {
    const { container } = render(<RefundPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
