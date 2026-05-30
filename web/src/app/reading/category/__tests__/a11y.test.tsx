/**
 * axe-core WCAG 2.1 AA scan for /reading/category (ISSUE-030, NFR-012).
 *
 * One scan per page is the project convention (cf. onboarding a11y test). The
 * `color-contrast` rule is disabled because jsdom does not compute real CSS —
 * the design system already passes contrast at the token level (covered by
 * the preview a11y test).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import CategoryPage from "@/app/reading/category/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

describe("/reading/category — WCAG 2.1 AA", () => {
  beforeEach(() => {
    useOnboardingStore.getState().reset();
  });

  it("has zero axe violations on the default (non-member) render", async () => {
    const { container } = render(<CategoryPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
