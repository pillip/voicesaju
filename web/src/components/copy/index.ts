/**
 * Copy tone system — barrel export. ISSUE-097 / FR-043.
 *
 * Re-exports the typographic primitives that operationalise the
 * "누님이 횡설수설" voice. Consumers import from `@/components/copy`
 * rather than reaching into individual files.
 *
 *   import { HandwrittenPrice, HandwrittenNote, SignedMark, Pause } from '@/components/copy';
 *
 * The companion stylesheet (`web/src/styles/copy-system.css`) provides
 * the global `article em` marker rule and the `data-pause` leading
 * adjustment. Mount it once at the app root (already wired via
 * `app/layout.tsx`).
 */

export { HandwrittenPrice } from './HandwrittenPrice';
export type { HandwrittenPriceProps } from './HandwrittenPrice';
export { HandwrittenNote } from './HandwrittenNote';
export type { HandwrittenNoteProps } from './HandwrittenNote';
export { SignedMark } from './SignedMark';
export type { SignedMarkProps } from './SignedMark';
export { Pause } from './Pause';
export type { PauseProps } from './Pause';
