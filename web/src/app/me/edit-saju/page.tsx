'use client';

/**
 * `/me/edit-saju` — Screen 21 (ISSUE-071, FR-029): route entry point.
 *
 * Next 15 forbids any named exports from a `page.tsx` other than the
 * small allowlist of route-config symbols. The real view + its test
 * surface live in `./MeEditSajuView.tsx`; this module is a thin
 * wrapper that just forwards to it so the build's Page-export check
 * passes.
 */

import { MeEditSajuView } from './MeEditSajuView';

export default function MeEditSajuPage() {
  return <MeEditSajuView />;
}
