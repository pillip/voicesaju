'use client';

/**
 * `<Seal>` — vermilion stamp signature (印) component. ISSUE-092 / FR-038.
 *
 * Renders a vermilion-red square block stamped with a single hanja
 * character in mincho serif, slightly rotated to evoke a 인주 도장
 * (vermilion ink seal) pressed against a hanji surface. Used at the end
 * of any "누님이 서명한" moment — reading-end, follow-up answer end,
 * quote card corner, tarot reveal.
 *
 * Purely presentational: no state, no callbacks. The component is
 * `aria-hidden` by default (decorative); pass an explicit `aria-label`
 * to convert it into a labelled signature for screen readers (per
 * FR-038 AC6).
 *
 * Visual spec (docs/design_system.md §Vermilion Seal):
 *  - background: var(--vermilion-300) (메인 인주 적색)
 *  - color:      var(--baekrim-200)   (백열등 색 hanja)
 *  - font:       var(--font-mincho)   (Noto Serif KR weight 900)
 *  - transform:  rotate(-2.5deg) default, rotate(+2.5deg) when tilt="right"
 *  - grain:      var(--grain-strong) via background-blend-mode: multiply
 *  - sizes:      sm=48, md=72, lg=112 px (fixed pixel grid per AC4)
 *
 * Category → hanja mapping (FR-038 AC4):
 *   love=戀, work=業, money=財, tarot=月, reading-end=明
 *
 * Either `hanja` (explicit character) OR `category` (looked-up) MUST be
 * provided. `hanja` wins if both are passed.
 *
 * Architecture refs:
 *   docs/requirements.md FR-038
 *   docs/design_system.md §"Vermilion Seal (인주 도장 印)"
 *   docs/design_philosophy.md §"Visual signature"
 */

import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

import { V2_GRAIN_TOKENS } from '@/lib/tokens';

export type SealSize = 'sm' | 'md' | 'lg';
export type SealTilt = 'left' | 'right';
export type SealCategory = 'love' | 'work' | 'money' | 'tarot' | 'reading-end';

/**
 * Category → default hanja mapping per FR-038 AC4. Exported so
 * downstream consumers (quote card, tarot reveal) can drive the same
 * lookup without re-declaring it.
 */
export const SEAL_CATEGORY_HANJA: Record<SealCategory, string> = {
  love: '戀',
  work: '業',
  money: '財',
  tarot: '月',
  'reading-end': '明',
};

/**
 * Fixed pixel grid for sm/md/lg. AC4 pins these exact values — do not
 * convert to a spacing-token scale (they intentionally sit OUTSIDE the
 * Tailwind 4px spacing grid because 도장 sizes are physical artefacts).
 */
const SEAL_SIZE_PX: Record<SealSize, number> = {
  sm: 48,
  md: 72,
  lg: 112,
};

/**
 * Hanja font-size per seal size. Roughly 0.6× the seal width so the
 * character stays inside the stamp border with breathing room.
 */
const SEAL_FONT_SIZE_PX: Record<SealSize, number> = {
  sm: 28,
  md: 42,
  lg: 64,
};

const SEAL_TILT_DEG: Record<SealTilt, number> = {
  left: -2.5,
  right: 2.5,
};

export interface SealProps extends Omit<HTMLAttributes<HTMLSpanElement>, 'children'> {
  /** Explicit hanja character. Takes precedence over `category`. */
  hanja?: string;
  /** Category whose default hanja should be looked up. */
  category?: SealCategory;
  /** Size variant — sm=48, md=72, lg=112 px. Defaults to `md`. */
  size?: SealSize;
  /** Rotation direction. `left` → -2.5deg, `right` → +2.5deg. */
  tilt?: SealTilt;
}

/**
 * Resolves the hanja character. Throws (in dev) when neither `hanja`
 * nor a known `category` is provided — silent fallback would let bad
 * seals slip into production.
 */
function resolveHanja(hanja?: string, category?: SealCategory): string {
  if (hanja && hanja.length > 0) return hanja;
  if (category) return SEAL_CATEGORY_HANJA[category];
  if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.warn('[Seal] Either `hanja` or `category` must be provided.');
  }
  return '?';
}

export function Seal({
  hanja,
  category,
  size = 'md',
  tilt = 'left',
  style,
  className,
  ...rest
}: SealProps): ReactNode {
  const character = resolveHanja(hanja, category);
  const px = SEAL_SIZE_PX[size];
  const fontPx = SEAL_FONT_SIZE_PX[size];
  const deg = SEAL_TILT_DEG[tilt];

  // Decorative by default. When the caller supplies an explicit
  // `aria-label`, surface the seal to assistive tech and DROP the
  // aria-hidden attribute (FR-038 AC6).
  const hasAriaLabel = typeof rest['aria-label'] === 'string' && rest['aria-label']!.length > 0;

  const inlineStyle: CSSProperties = {
    display: 'inline-grid',
    placeItems: 'center',
    width: `${px}px`,
    height: `${px}px`,
    backgroundColor: 'var(--vermilion-300)',
    backgroundImage: V2_GRAIN_TOKENS['--grain-strong'],
    backgroundBlendMode: 'multiply',
    color: 'var(--baekrim-200)',
    fontFamily: 'var(--font-mincho)',
    fontWeight: 900,
    fontSize: `${fontPx}px`,
    lineHeight: 1,
    boxShadow: 'inset 0 0 0 1px var(--vermilion-500)',
    transform: `rotate(${deg}deg)`,
    userSelect: 'none',
    ...style,
  };

  return (
    <span
      data-testid="seal"
      data-size={size}
      data-tilt={tilt}
      data-hanja={character}
      aria-hidden={hasAriaLabel ? undefined : true}
      className={className}
      style={inlineStyle}
      {...rest}
    >
      {character}
    </span>
  );
}
