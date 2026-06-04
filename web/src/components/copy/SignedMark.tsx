'use client';

/**
 * `<SignedMark>` — "signed, 누님" + 印 stamp end-of-utterance signature.
 * ISSUE-097 / FR-043.
 *
 * Renders the canonical sign-off used at the end of every reading and
 * follow-up answer: the italic mincho phrase `signed, 누님` followed by
 * a small vermilion `<Seal hanja="明" />`. Mounted at the bottom of
 * `/reading/play` (the ended state) and `/reading/end` per AC3.
 *
 * The seal child is wrapped in `React.memo` so re-renders of the
 * surrounding tree (which happen often on /reading/play because of
 * audio progress + subtitle updates) don't churn the seal's inline
 * style object. The brief explicitly calls out memoisation here.
 *
 * Visual spec (docs/design_system.md §Typography + §Copy Tone):
 *   font:       var(--font-mincho)   — Noto Serif KR weight 900
 *   color:      var(--cream-300)
 *   style:      italic
 *   children layout: inline-flex, gap-8px, vertical-align baseline
 *
 * Accessibility:
 *   The seal is decorative (per <Seal>'s default aria-hidden=true), so
 *   the SR announcement is just "signed, 누님". This matches the spoken
 *   intent — the seal is the visual punctuation, not an information
 *   token.
 *
 * Architecture refs:
 *   docs/copy_guide.md §Voice & Tone
 *   docs/design_system.md §Typography
 *   docs/interactions.md §Flow F
 */

import { memo, type CSSProperties, type HTMLAttributes, type ReactNode } from 'react';

import { Seal } from '@/components/seal';

/**
 * Memoised vermilion seal — `<SignedMark>` mounts at the end of every
 * reading + follow-up, so a stable identity for this subtree keeps
 * React from re-rendering the stamp on every parent state tick.
 *
 * The seal is intentionally fixed at hanja="明" + size="sm" + tilt
 * default — this is the canonical sign-off seal, not a configurable
 * slot.
 */
const SignedMarkSeal = memo(function SignedMarkSeal(): ReactNode {
  return <Seal hanja="明" size="sm" />;
});

// Plain alias to `HTMLAttributes<HTMLSpanElement>` — ESLint's
// `no-empty-object-type` rule forbids the equivalent empty-interface
// form, but we still want a named type for the public API.
export type SignedMarkProps = HTMLAttributes<HTMLSpanElement>;

export function SignedMark({ style, className, ...rest }: SignedMarkProps): ReactNode {
  const inlineStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'baseline',
    gap: '8px',
    fontFamily: 'var(--font-mincho)',
    fontStyle: 'italic',
    color: 'var(--cream-300)',
    ...style,
  };

  return (
    <span
      data-testid="signed-mark"
      data-copy-primitive="signed-mark"
      className={className}
      style={inlineStyle}
      {...rest}
    >
      <span data-testid="signed-mark-text">signed, 누님</span>
      <SignedMarkSeal />
    </span>
  );
}
