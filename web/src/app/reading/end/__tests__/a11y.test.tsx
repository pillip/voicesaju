/**
 * axe-core WCAG 2.1 AA scan for `/reading/end` (ISSUE-059).
 *
 * We mount the same `<EndClient>` the page renders, mock the heavy
 * presentational children, and let axe walk the resulting DOM. The
 * mocked children expose `data-testid` placeholders so the page's own
 * semantic shell (landmarks, headings, CTA labels) is what gets scanned.
 *
 * `color-contrast` is disabled because jsdom doesn't compute real CSS
 * contrast — that surface is covered by the design-system preview test.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

import { RuntimeProvider } from "@/lib/context/runtime-context";
import type { QuoteCardBySlugResponse } from "@/app/api/og/[slug]/og-helpers";

vi.mock("@/components/share/QuoteCardPreview", () => ({
  QuoteCardPreview: () => (
    <div
      role="img"
      aria-label="공유된 명대사 카드 (mock)"
      data-testid="mock-qcp"
    />
  ),
}));
vi.mock("@/components/share/ShareButtonRow", () => ({
  ShareButtonRow: () => (
    <div role="group" aria-label="공유" data-testid="mock-sbr">
      <button type="button">인스타 스토리</button>
      <button type="button">카톡</button>
      <button type="button">저장</button>
    </div>
  ),
}));

vi.mock("next/navigation", async () => {
  const actual =
    await vi.importActual<typeof import("next/navigation")>("next/navigation");
  return {
    ...actual,
    useSearchParams: () => ({
      get: (key: string) => (key === "slug" ? "abc123" : null),
    }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  };
});

import EndClient from "../EndClient";

expect.extend(toHaveNoViolations);

const axeRules = {
  "color-contrast": { enabled: false },
};

const sampleCard: QuoteCardBySlugResponse = {
  quote_card_id: "qc-1",
  category: "love",
  character_key: "nuna",
  quote_text: "그 사람은 너랑 코드가 안 맞아.",
  og_status: "baked",
  og_r2_key: "og/qc-1.png",
};

describe("/reading/end — WCAG 2.1 AA", () => {
  beforeEach(() => {
    Object.defineProperty(window.navigator, "userAgent", {
      value:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("has zero axe violations on the happy-path render", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(sampleCard), { status: 200 }),
    );

    let container: HTMLElement | null = null;
    await act(async () => {
      const result = render(
        <RuntimeProvider>
          <EndClient />
        </RuntimeProvider>,
      );
      container = result.container;
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const results = await axe(container as unknown as HTMLElement, {
      rules: axeRules,
    });
    expect(results).toHaveNoViolations();
  }, 15000);
});
