/**
 * Unit tests for `/legal/terms` (ISSUE-074, FR-036 AC1).
 *
 * AC mapping:
 *   - Renders the page chrome (back-to-home link + title).
 *   - Body contains the "오락 목적" disclaimer (the AC-critical phrase).
 *   - Body links out to /legal/privacy and /legal/refund.
 *   - Zero axe-core violations (NFR-012).
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

import TermsPage from "@/app/legal/terms/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  // jsdom doesn't compute real CSS; design tokens are validated separately.
  "color-contrast": { enabled: false },
};

describe("/legal/terms", () => {
  it("renders the title and back-to-home affordance", () => {
    render(<TermsPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "이용약관" }),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "홈으로 돌아가기" })).toBeTruthy();
  });

  it('includes the "오락 목적" disclaimer (FR-036 AC1)', () => {
    const { container } = render(<TermsPage />);
    // The disclaimer appears at least twice (heading + body) — assert
    // presence rather than count so copy edits don't break the test.
    expect(container.textContent).toContain("오락 목적");
  });

  it("links to the privacy and refund policies", () => {
    render(<TermsPage />);
    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain("/legal/privacy");
    expect(hrefs).toContain("/legal/refund");
  });

  it("has zero axe violations", async () => {
    const { container } = render(<TermsPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
