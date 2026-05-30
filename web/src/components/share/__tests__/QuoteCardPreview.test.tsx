/**
 * Unit tests for {@link QuoteCardPreview} — Screen 11 quote card surface
 * used by `/reading/end` (ISSUE-059).
 *
 * AC coverage:
 *  - AC1 (card load): renders an `<img src="/api/og/{slug}">` once the
 *    backend payload has a non-failed `og_status`.
 *  - Loading: renders the skeleton when `card === undefined` (still
 *    fetching).
 *  - Error fallback (copy_guide §9 — "공유 미리보기가 안 보일 수 있어"):
 *    when `og_status === 'failed'`, render the static category-colored
 *    fallback card + the small advisory caption from copy_guide. The
 *    user must still be able to share what's shown (per copy_guide).
 *
 * We render with React Testing Library and inspect the DOM directly —
 * the component is a small presentational unit, no async work, no
 * external SDK to mock.
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { QuoteCardPreview } from "@/components/share/QuoteCardPreview";
import type { QuoteCardBySlugResponse } from "@/app/api/og/[slug]/og-helpers";

const baseCard: QuoteCardBySlugResponse = {
  quote_card_id: "qc-1",
  category: "love",
  character_key: "nuna",
  quote_text: "그 사람은 너랑 코드가 안 맞아.",
  og_status: "baked",
  og_r2_key: "og/qc-1.png",
};

describe("QuoteCardPreview", () => {
  it("renders the OG image once the card is baked (AC1)", () => {
    render(<QuoteCardPreview slug="abc123" card={baseCard} />);
    const img = screen.getByRole("img", { name: /명대사 카드/ });
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("src")).toBe("/api/og/abc123");
  });

  it("renders a skeleton when the card is still loading", () => {
    render(<QuoteCardPreview slug="abc123" card={undefined} />);
    expect(screen.getByTestId("quote-card-skeleton")).toBeInTheDocument();
    // No image should be present in the loading state.
    expect(screen.queryByRole("img", { name: /명대사 카드/ })).toBeNull();
  });

  it("renders the static fallback + advisory caption when og_status is failed", () => {
    render(
      <QuoteCardPreview
        slug="abc123"
        card={{ ...baseCard, og_status: "failed", og_r2_key: null }}
      />,
    );
    // Fallback panel exists — it shows the quote text directly because we
    // can't show the baked image.
    expect(screen.getByTestId("quote-card-fallback")).toBeInTheDocument();
    expect(screen.getByText(baseCard.quote_text)).toBeInTheDocument();
    // Advisory caption from copy_guide §9 Error: OG 이미지 생성 실패.
    expect(
      screen.getByText("공유 미리보기가 안 보일 수 있어. 저장은 돼."),
    ).toBeInTheDocument();
  });
});
