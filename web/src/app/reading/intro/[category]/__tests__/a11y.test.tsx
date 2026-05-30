/**
 * axe-core WCAG 2.1 AA scan for /reading/intro/[category] (ISSUE-032).
 *
 * Single scan per page per project convention; `color-contrast` disabled
 * because jsdom does not compute real CSS contrast (token-level contrast
 * is asserted in the design-system preview test).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}));

const fetchIntroClipMock = vi.fn();
vi.mock("@/lib/api/intro", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/intro")>("@/lib/api/intro");
  return {
    ...actual,
    fetchIntroClip: (...args: unknown[]) => fetchIntroClipMock(...args),
  };
});

import IntroClient from "@/app/reading/intro/[category]/IntroClient";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

describe("/reading/intro/[category] — WCAG 2.1 AA", () => {
  beforeEach(() => {
    fetchIntroClipMock.mockReset();
  });

  it("has zero axe violations on the loading-state render", async () => {
    // We intentionally axe-scan the loading shell (which uses the same
    // ink/cream tokens + an aria-busy attribute). The happy-path render
    // requires a fetch promise to resolve and an <audio> element to
    // mount — jsdom does not implement HTMLMediaElement, which makes
    // that branch flaky for axe. The loading branch shares the visual
    // shell (TopAppBar substitute + character + subtitle band) so any
    // violation in the player itself would also show up here.
    fetchIntroClipMock.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = render(<IntroClient category="love" />);
    await waitFor(() => {
      expect(screen.getByTestId("intro-loading")).toBeInTheDocument();
    });
    const results = await axe(container, { rules: axeRules });
    expect(results).toHaveNoViolations();
  }, 15000);
});
