'use client';

/**
 * `<Pause />` — typographic pause / paragraph breath. ISSUE-097 / FR-043.
 *
 * The "누님" voice writes in short single-sentence beats with deliberate
 * gaps between them — the gap is itself part of the copy. `<Pause />`
 * renders a `<br data-pause>` element; the global `@layer copy-system`
 * rule in `copy-system.css` adjusts the leading on lines that follow a
 * `data-pause` break so the silence reads visually.
 *
 * Use it inline inside paragraph copy:
 *
 *     <p>
 *       흠.
 *       <Pause />
 *       이 시간에 사주를 본다고?
 *     </p>
 *
 * No props, no children — `<br>` is a void element. The `data-pause`
 * attribute is the single hook for the CSS rule + for tests.
 *
 * Accessibility:
 *   Screen readers honour `<br>` as a line break + brief pause already;
 *   no extra ARIA needed. The visual leading is purely decorative.
 *
 * Architecture refs:
 *   docs/copy_guide.md §Voice & Tone
 *   docs/design_system.md §Typography
 */

import type { ReactNode } from 'react';

export interface PauseProps {
  /** Optional id passthrough so tests / a11y tooling can target a specific pause. */
  id?: string;
}

export function Pause({ id }: PauseProps = {}): ReactNode {
  return <br data-pause data-testid="pause" id={id} />;
}
