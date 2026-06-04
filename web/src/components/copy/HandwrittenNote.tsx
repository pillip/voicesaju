'use client';

/**
 * `<HandwrittenNote>` — brush-script aside / inline annotation. ISSUE-097
 * / FR-043.
 *
 * The "누님이 횡설수설" voice often scribbles a side remark on the
 * margin — a quick "흠… 진심이긴 해" next to a serious sentence. This
 * primitive renders that scribble in the same brush font as
 * `<HandwrittenPrice>` but in cream (not vermilion) so it reads as an
 * aside, not a stamp.
 *
 * Visual spec (docs/design_system.md §Typography + §Copy Tone):
 *   font:       var(--font-brush)
 *   color:      var(--cream-300)
 *   transform:  rotate({tilt}deg)  — default tilt = -1.5
 *   line-height: 1.1                 — slightly looser than the price
 *
 * Tilt prop:
 *   The brief calls out -1.5 (default) and -3 as the two canonical
 *   tilts. We accept any number so future variants stay open without a
 *   component change. Passing `tilt={-3}` produces `rotate(-3deg)` in
 *   the computed transform, satisfying AC2.
 *
 * Tilt stays inline — same rationale as `<HandwrittenPrice>`. ISSUE-098
 * owns the global `.tilted` utility.
 *
 * Accessibility:
 *   The note is text content; screen readers announce the children
 *   verbatim. Callers may attach `aria-label` to override (e.g. on the
 *   end-of-reading farewell scribble where the rendered text is short
 *   and benefits from a fuller spoken form).
 *
 * Architecture refs:
 *   docs/copy_guide.md §Voice & Tone
 *   docs/design_system.md §Typography
 */

import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

export interface HandwrittenNoteProps extends HTMLAttributes<HTMLSpanElement> {
  /** Rotation in degrees. Negative tilts the note up to the left. Default -1.5. */
  tilt?: number;
  children: ReactNode;
}

export function HandwrittenNote({
  tilt = -1.5,
  style,
  className,
  children,
  ...rest
}: HandwrittenNoteProps): ReactNode {
  const inlineStyle: CSSProperties = {
    display: 'inline-block',
    fontFamily: 'var(--font-brush)',
    color: 'var(--cream-300)',
    transform: `rotate(${tilt}deg)`,
    lineHeight: 1.1,
    ...style,
  };

  return (
    <span
      data-testid="handwritten-note"
      data-copy-primitive="handwritten-note"
      data-tilt={tilt}
      className={className}
      style={inlineStyle}
      {...rest}
    >
      {children}
    </span>
  );
}
