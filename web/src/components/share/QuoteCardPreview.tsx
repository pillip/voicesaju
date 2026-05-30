"use client";

/**
 * `<QuoteCardPreview>` — the quote-card surface for Screen 11
 * (`/reading/end`, ISSUE-059).
 *
 * Three rendering states:
 *
 *   1. Loading (`card === undefined`)
 *      → skeleton (shimmer-free placeholder; the design system has no
 *        animated shimmer primitive yet — a static box is enough for
 *        the < 3s window before the backend lookup resolves).
 *
 *   2. Baked / pending (`og_status !== 'failed'`)
 *      → full-bleed `<img src="/api/og/{slug}">`. We use the same edge
 *        route the social crawler hits (ISSUE-060), so the share path
 *        and the in-app render share one cache key.
 *
 *   3. Failed (`og_status === 'failed'`)
 *      → static category-colored fallback panel rendering the quote
 *        text directly + the small "공유 미리보기가 안 보일 수 있어. 저장은
 *        돼." advisory from `docs/copy_guide.md` §9. Per FR-018 AC the
 *        share buttons must still work — that's enforced by the parent,
 *        not here.
 *
 * Architecture-Ref: docs/ux_spec.md Screen 11, docs/copy_guide.md §9.
 */

import { cn } from "@/lib/utils";
import type { QuoteCardBySlugResponse } from "@/app/api/og/[slug]/og-helpers";

/**
 * Category → background colour, mirroring `og-helpers.tsx` `CATEGORY_BG`
 * and the Pillow bake worker. Tailwind class names map to the same hex
 * values; we use classes here so the design-system tokens stay the
 * single source of truth.
 *
 * The bake palette is per A-06:
 *   love  → #FFB6C1  → soft pink
 *   work  → #87CEEB  → sky blue
 *   money → #FFD700  → gold
 *   tarot → #9370DB  → medium purple
 *
 * The Tailwind palette doesn't have exact matches, so we use inline
 * `style.background` — this keeps the fallback visually consistent with
 * the baked image when both are visible side-by-side.
 */
const CATEGORY_BG: Record<string, string> = {
  love: "#FFB6C1",
  work: "#87CEEB",
  money: "#FFD700",
  tarot: "#9370DB",
};

const FALLBACK_BG = "#E0E0E0";

export interface QuoteCardPreviewProps {
  /** Share slug — drives the `<img>` src `/api/og/{slug}`. */
  slug: string;
  /**
   * Quote-card payload from `/api/v1/quote-cards/by-slug/{slug}`.
   * `undefined` means the fetch is still in flight → render skeleton.
   */
  card: QuoteCardBySlugResponse | undefined;
  className?: string;
}

export function QuoteCardPreview({
  slug,
  card,
  className,
}: QuoteCardPreviewProps) {
  // 1) Loading state.
  if (card === undefined) {
    return (
      <div
        data-testid="quote-card-skeleton"
        aria-busy="true"
        aria-label="명대사 카드를 불러오는 중"
        className={cn(
          "aspect-[9/16] w-full max-w-sm rounded-lg bg-ink-700/60",
          className,
        )}
      />
    );
  }

  // 3) Failed state — static fallback.
  if (card.og_status === "failed") {
    const bg = CATEGORY_BG[card.category] ?? FALLBACK_BG;
    return (
      <div
        className={cn(
          "flex w-full max-w-sm flex-col items-center gap-s3",
          className,
        )}
      >
        <div
          data-testid="quote-card-fallback"
          role="img"
          aria-label={`명대사 카드 (대체): ${card.quote_text}, 카테고리: ${card.category}`}
          className="flex aspect-[9/16] w-full flex-col items-center justify-center rounded-lg px-s4 py-s6 text-center shadow-lg"
          style={{ backgroundColor: bg }}
        >
          <p className="font-display text-2xl font-bold leading-snug text-ink-900">
            {card.quote_text}
          </p>
          <p className="mt-s6 font-body text-sm text-ink-900/60">VoiceSaju</p>
        </div>
        <p className="font-body text-xs text-cream-300">
          공유 미리보기가 안 보일 수 있어. 저장은 돼.
        </p>
      </div>
    );
  }

  // 2) Baked / pending — render the OG image. Even `pending` shows the
  //    edge route's inline fallback (ISSUE-060), so the user never sees
  //    a blank card while the bake worker is mid-flight.
  const ogImageUrl = `/api/og/${slug}`;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={ogImageUrl}
      alt={`명대사 카드: ${card.quote_text}, 카테고리: ${card.category}`}
      width={1080}
      height={1920}
      data-testid="quote-card-img"
      className={cn(
        "aspect-[9/16] w-full max-w-sm rounded-lg shadow-lg",
        className,
      )}
    />
  );
}
