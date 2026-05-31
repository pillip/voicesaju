/**
 * Unit tests for `/legal/privacy` (ISSUE-074, FR-036 AC2).
 *
 * AC mapping:
 *   - Renders title + back-to-home affordance.
 *   - Body mentions AES-256 birth date encryption (the AC-critical claim).
 *   - Body mentions Toss Payments as the payment data processor.
 *   - Zero axe-core violations (NFR-012).
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

import PrivacyPage from "@/app/legal/privacy/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

describe("/legal/privacy", () => {
  it("renders the title and back-to-home affordance", () => {
    render(<PrivacyPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "개인정보처리방침" }),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "홈으로 돌아가기" })).toBeTruthy();
  });

  it("mentions AES-256 birth date encryption (FR-036 AC2)", () => {
    const { container } = render(<PrivacyPage />);
    expect(container.textContent).toContain("AES-256");
    // The birth-date-encryption claim is the AC-critical phrase, not just
    // the algorithm name — assert the surrounding context too.
    expect(container.textContent).toMatch(/생년월일|출생/);
  });

  it("mentions Toss Payments as a payment data processor (FR-036 AC2)", () => {
    const { container } = render(<PrivacyPage />);
    expect(container.textContent).toMatch(/토스페이먼츠|Toss Payments/);
  });

  it("has zero axe violations", async () => {
    const { container } = render(<PrivacyPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
