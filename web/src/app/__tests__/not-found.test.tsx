/**
 * Unit tests for the global `not-found.tsx` (ISSUE-075, FR-035).
 *
 * AC mapping:
 *   - Renders the friendly Korean copy + home CTA.
 *   - The home CTA is a real anchor with href="/".
 *   - Zero axe-core violations (NFR-012).
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

import NotFound from "@/app/not-found";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

describe("not-found.tsx (global 404)", () => {
  it("renders the friendly copy + home CTA", () => {
    render(<NotFound />);
    expect(screen.getByTestId("not-found")).toBeTruthy();
    expect(screen.getByText("길을 잘못 들었네…")).toBeTruthy();
    const cta = screen.getByTestId("not-found-home");
    expect(cta.getAttribute("href")).toBe("/");
  });

  it("has zero axe violations", async () => {
    const { container } = render(<NotFound />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
