'use client';

/**
 * `<HanjaMonument>` — hero-scale 한자 주연 디스플레이 (FR-039 / ISSUE-093).
 *
 * Single-character monumental display used across landing, onboarding
 * 1-3, category, reading-play, and `/me/saju` per docs/wireframes.md.
 * The character renders at `font-size: clamp(120px, 28vw, 240px)` in
 * `--font-mincho` so it scales fluidly from mobile (375 px → ~105 px
 * clamped to the 120 px floor) up to desktop (1280 px → 240 px ceiling).
 *
 * Token + spec source: docs/design_system.md §"Hanja Monument" + FR-039.
 *
 * Color note: ISSUE-093's spec line said `--hanji-900` but that token is
 * the vignette-edge near-black (`#0A0604`) and would be invisible on the
 * hanji-800 base. design_system.md §"Hanja Monument" uses
 * `--baekrim-200` (`#D9C49A`, 백열등 색) — that's the source-of-truth and
 * what's used here. (FR-039 review caught the inconsistency, fix is
 * inline; a follow-up doc fix should reword the issue's AC1.)
 *
 * The character set supported at launch (FR-039 AC4):
 *   命 生 時 性 戀 業 財 月 我 門
 *
 * Decorative by default (`aria-hidden`); pass an explicit `aria-label`
 * to surface it to assistive tech as a labelled landmark.
 */

import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

/**
 * Characters explicitly verified against the FR-039 AC4 set. Other
 * characters render fine (the component is purely presentational) but
 * this constant is exported so tests / consumers can assert on the
 * supported set without re-typing it.
 */
export const HANJA_MONUMENT_CHAR_SET = [
  '命',
  '生',
  '時',
  '性',
  '戀',
  '業',
  '財',
  '月',
  '我',
  '門',
] as const;

export type HanjaMonumentChar = (typeof HANJA_MONUMENT_CHAR_SET)[number];

export interface HanjaMonumentProps extends Omit<HTMLAttributes<HTMLSpanElement>, 'children'> {
  /** Hanja character to display. */
  char: string;
  /**
   * When `true` (default), trims the visual margins via `--cut` so the
   * character can bleed off the edge per design_system.md
   * §"hanja-monument--cut". Pass `false` for centred display.
   */
  cut?: boolean;
}

export function HanjaMonument({
  char,
  cut = true,
  style,
  className,
  ...rest
}: HanjaMonumentProps): ReactNode {
  const hasAriaLabel = typeof rest['aria-label'] === 'string' && rest['aria-label']!.length > 0;

  const inlineStyle: CSSProperties = {
    display: 'inline-block',
    fontFamily: 'var(--font-mincho)',
    fontWeight: 900,
    // FR-039 AC1: fluid scale from 120px (≤ 429px viewports) to 240px
    // (≥ 858px viewports). 28vw is the linear gradient between.
    fontSize: 'clamp(120px, 28vw, 240px)',
    lineHeight: 0.85,
    letterSpacing: '-0.04em',
    color: 'var(--baekrim-200)',
    textShadow: '0 0 30px rgba(155, 42, 26, 0.08)',
    // `--cut` bleed — pulls the character into negative margin so it
    // can sit half-off the container edge (intentional uncanny crop
    // per design_system.md).
    ...(cut ? { marginLeft: '-0.15em', marginRight: '-0.1em' } : null),
    ...style,
  };

  return (
    <span
      data-testid="hanja-monument"
      data-char={char}
      aria-hidden={hasAriaLabel ? undefined : true}
      className={className}
      style={inlineStyle}
      {...rest}
    >
      {char}
    </span>
  );
}
