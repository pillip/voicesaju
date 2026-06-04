'use client';

/**
 * `<QuoteCardPreview>` — the quote-card surface for Screen 11
 * (`/reading/end`, ISSUE-059) + `/tarot/end`.
 *
 * Two visual variants:
 *
 *   v="v1" (default — ISSUE-058/059):
 *     - Loading (`card === undefined`) → skeleton.
 *     - Baked / pending → full-bleed `<img src="/api/og/{slug}">`.
 *     - Failed → static category-colored fallback panel.
 *
 *   v="v2" (ISSUE-095, gated by `NEXT_PUBLIC_QUOTE_CARD_V2`):
 *     - Loading → same skeleton (parity with v1).
 *     - Baked / pending → client-side composited card with:
 *         · 8 px borderline in the per-category v2 palette
 *           (love=#B7414B / work=#16344E / money=#B68B3F / tarot=#5A3666)
 *         · -1.5deg auto-tilt
 *         · `--grain-strong` overlay with background-blend-mode: multiply
 *         · vermilion `<Seal>` (size md, tilt=right) bottom-right with
 *           the FR-038 category-hanja mapping
 *         · quote text in baekrim-200 mincho
 *     - Failed → same static fallback as v1 (failure UX shared).
 *
 * The `v` prop is set by the caller after consulting
 * `isQuoteCardV2Enabled()` so the flag is honoured server-side at
 * page-render time without forcing a client-side env lookup here.
 *
 * Architecture-Ref: docs/ux_spec.md Screen 11, docs/copy_guide.md §9,
 * docs/design_system.md §"QuoteCard v2".
 */

import type { CSSProperties } from 'react';

import { Seal } from '@/components/seal/Seal';
import { V2_GRAIN_TOKENS } from '@/lib/tokens';
import { OG_LAYOUT_V2, v2BorderColorForCategory, v2SealHanjaForCategory } from '@/lib/ogLayoutV2';
import { cn } from '@/lib/utils';
import type { QuoteCardBySlugResponse } from '@/app/api/og/[slug]/og-helpers';

/**
 * v1 category → background hex. Mirrors `og-helpers.tsx` `CATEGORY_BG`
 * and the Pillow bake worker (kept for the failure-state fallback panel
 * which both v1 and v2 share).
 */
const CATEGORY_BG: Record<string, string> = {
  love: '#FFB6C1',
  work: '#87CEEB',
  money: '#FFD700',
  tarot: '#9370DB',
};

const FALLBACK_BG = '#E0E0E0';

export type QuoteCardPreviewVariant = 'v1' | 'v2';

export interface QuoteCardPreviewProps {
  /** Share slug — drives the `<img>` src `/api/og/{slug}` (v1). */
  slug: string;
  /**
   * Quote-card payload from `/api/v1/quote-cards/by-slug/{slug}`.
   * `undefined` means the fetch is still in flight → render skeleton.
   */
  card: QuoteCardBySlugResponse | undefined;
  /**
   * Visual variant. v1 = legacy `<img>` (ISSUE-058/059). v2 = client
   * composited 9:16 card with vermilion seal (ISSUE-095). Defaults to
   * v1 so the rollback path stays the no-op.
   */
  v?: QuoteCardPreviewVariant;
  className?: string;
}

export function QuoteCardPreview({ slug, card, v = 'v1', className }: QuoteCardPreviewProps) {
  // 1) Loading state — shared by v1 and v2.
  if (card === undefined) {
    return (
      <div
        data-testid="quote-card-skeleton"
        aria-busy="true"
        aria-label="명대사 카드를 불러오는 중"
        className={cn('aspect-[9/16] w-full max-w-sm rounded-lg bg-ink-700/60', className)}
      />
    );
  }

  // 3) Failed state — shared by v1 and v2 (the failure UX is the same
  //    regardless of v2 rollout; the fallback advisory copy comes from
  //    copy_guide §9).
  if (card.og_status === 'failed') {
    const bg = CATEGORY_BG[card.category] ?? FALLBACK_BG;
    return (
      <div className={cn('flex w-full max-w-sm flex-col items-center gap-s3', className)}>
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

  // 2a) Baked / pending — v2 client-side composited variant.
  if (v === 'v2') {
    return <QuoteCardPreviewV2 card={card} className={className} />;
  }

  // 2b) Baked / pending — legacy v1 image variant.
  const ogImageUrl = `/api/og/${slug}`;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={ogImageUrl}
      alt={`명대사 카드: ${card.quote_text}, 카테고리: ${card.category}`}
      width={1080}
      height={1920}
      data-testid="quote-card-img"
      className={cn('aspect-[9/16] w-full max-w-sm rounded-lg shadow-lg', className)}
    />
  );
}

// ---------------------------------------------------------------------------
// v2 sub-component — ISSUE-095
// ---------------------------------------------------------------------------

interface QuoteCardPreviewV2Props {
  card: QuoteCardBySlugResponse;
  className?: string;
}

/**
 * Client-side composited 9:16 quote card following the v2 spec. The
 * canvas is a hanji-800 panel with a per-category border, -1.5deg auto
 * tilt, a `--grain-strong` overlay, and a vermilion seal stamped in the
 * bottom-right corner using the FR-038 hanja mapping.
 *
 * The internal layout numbers come from the same `og/layout_v2.json`
 * that drives the Pillow bake and the edge route, so the on-screen
 * preview and the shared OG asset stay visually consistent.
 */
function QuoteCardPreviewV2({ card, className }: QuoteCardPreviewV2Props) {
  const layout = OG_LAYOUT_V2;
  const borderColor = v2BorderColorForCategory(card.category);
  const sealHanja = v2SealHanjaForCategory(card.category);

  const cardStyle: CSSProperties = {
    backgroundColor: layout.canvas.background,
    borderStyle: 'solid',
    borderWidth: `${layout.border.width_px}px`,
    borderColor,
    transform: `rotate(${layout.tilt.rotate_deg}deg)`,
    transformOrigin: 'center center',
    position: 'relative',
    overflow: 'hidden',
  };

  const grainStyle: CSSProperties = {
    position: 'absolute',
    inset: 0,
    pointerEvents: 'none',
    backgroundImage: V2_GRAIN_TOKENS['--grain-strong'],
    backgroundBlendMode: layout.grain.blend_mode,
    mixBlendMode: 'multiply',
  };

  // Place the seal slot in absolute coordinates inside the card. The
  // bottom/right values use the layout JSON's margin scaled down to a
  // viewport-relative unit so the same proportions hold whether the
  // card is rendered at 1080×1920 (R2 cache) or ~360×640 (mobile view).
  const sealSlotStyle: CSSProperties = {
    position: 'absolute',
    bottom: '8%',
    right: '8%',
    zIndex: 2,
  };

  return (
    <div
      data-testid="quote-card-v2"
      data-cat={card.category}
      role="img"
      aria-label={`명대사 카드: ${card.quote_text}, 카테고리: ${card.category}`}
      className={cn(
        'aspect-[9/16] w-full max-w-sm rounded-sm shadow-2xl',
        'flex flex-col items-stretch justify-between px-s8 py-s10',
        'font-display text-baekrim-200',
        className,
      )}
      style={cardStyle}
    >
      {/* Grain overlay — sits between the canvas background and the
          content so the quote text isn't textured. */}
      <div
        data-testid="quote-card-v2-grain"
        data-grain-token={layout.grain.token}
        aria-hidden
        style={grainStyle}
      />

      {/* Quote band — centered vertically inside the card. */}
      <div
        data-testid="quote-card-v2-quote"
        className="relative z-10 flex flex-1 items-center justify-center px-s4 text-center"
        style={{
          color: layout.typography.quote_color,
          fontSize: 'clamp(1.25rem, 4vw, 1.75rem)',
          lineHeight: layout.typography.quote_line_height,
          fontWeight: 600,
        }}
      >
        <p>{card.quote_text}</p>
      </div>

      {/* Watermark — bottom-left, hanji-300 mono caps. */}
      <div
        className="relative z-10 self-start text-xs uppercase tracking-[0.16em]"
        style={{ color: layout.typography.watermark_color }}
      >
        VoiceSaju
      </div>

      {/* Seal corner — bottom-right vermilion stamp with category hanja. */}
      <div data-slot="seal" style={sealSlotStyle}>
        <Seal hanja={sealHanja} tilt={layout.seal.tilt} size="md" />
      </div>
    </div>
  );
}
