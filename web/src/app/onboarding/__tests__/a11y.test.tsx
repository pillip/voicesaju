/**
 * axe-core a11y scan across all 4 onboarding pages (ISSUE-028, NFR-012).
 *
 * One scan per step page — issue's Tests section asks for "axe-core a11y on
 * each step" and the Scope Management Guidance scopes a11y to one scan per
 * step page.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import BirthDatePage from "@/app/onboarding/birth-date/page";
import BirthTimePage from "@/app/onboarding/birth-time/page";
import GenderPage from "@/app/onboarding/gender/page";
import NamePage from "@/app/onboarding/name/page";

expect.extend(toHaveNoViolations);

const axeRules = {
  // color-contrast is unreliable in jsdom (no real CSS computation) — design
  // system tokens already pass 4.5:1 by construction (cf. preview a11y test).
  "color-contrast": { enabled: false },
};

describe("Onboarding pages — WCAG 2.1 AA", () => {
  beforeEach(() => {
    useOnboardingStore.getState().reset();
  });

  it("/onboarding/birth-date has zero axe violations", async () => {
    const { container } = render(<BirthDatePage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it("/onboarding/birth-time has zero axe violations", async () => {
    const { container } = render(<BirthTimePage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it("/onboarding/gender has zero axe violations", async () => {
    const { container } = render(<GenderPage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });

  it("/onboarding/name has zero axe violations", async () => {
    const { container } = render(<NamePage />);
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  });
});
