'use client';

/**
 * `<HandwrittenPrice>` — brush-script handwritten price tag. ISSUE-097 /
 * FR-043.
 *
 * The "누님이 횡설수설" voice writes prices the way someone scribbles
 * a number on a bar tab — slightly tilted, in vermilion ink, in a
 * handwritten brush font (Nanum Brush Script). Used wherever the
 * surface needs to feel hand-marked rather than typeset.
 *
 * Visual spec (docs/design_system.md §Typography + §Copy Tone):
 *   font:       var(--font-brush)   (Nanum Brush Script)
 *   color:      var(--vermilion-500) (도장 그림자 / 인주 깊은)
 *   transform:  rotate(-1.5deg)
 *   line-height: 1
 *
 * Tilt stays inline on the component — ISSUE-098 owns the global
 * `.tilted` utility surface and will promote this later if appropriate.
 * Do NOT depend on a shared `.tilted` class here.
 *
 * Accessibility:
 *   - The visual is purely decorative tilt + brush. The price *value*
 *     itself must still be announced verbatim. We render the `value`
 *     prop as plain text inside the span; if the caller supplies an
 *     `aria-label`, it overrides the announced text (e.g. "4900 원").
 *
 * Architecture refs:
 *   docs/copy_guide.md §Voice & Tone
 *   docs/design_system.md §Typography
 */

import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

export interface HandwrittenPriceProps extends Omit<HTMLAttributes<HTMLSpanElement>, 'children'> {
  /** Price string to render (e.g. "4,900원"). */
  value: string;
}

export function HandwrittenPrice({
  value,
  style,
  className,
  ...rest
}: HandwrittenPriceProps): ReactNode {
  const inlineStyle: CSSProperties = {
    display: 'inline-block',
    fontFamily: 'var(--font-brush)',
    color: 'var(--vermilion-500)',
    transform: 'rotate(-1.5deg)',
    lineHeight: 1,
    ...style,
  };

  return (
    <span
      data-testid="handwritten-price"
      data-copy-primitive="handwritten-price"
      className={className}
      style={inlineStyle}
      {...rest}
    >
      {value}
    </span>
  );
}
