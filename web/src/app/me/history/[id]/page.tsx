'use client';

/**
 * `/me/history/[id]` — Screen 19 (ISSUE-066): history player route.
 *
 * Next 15 places strict constraints on what a `page.tsx` may export:
 * only the default page component + a small allowlist of route-config
 * symbols. The actual view lives in
 * `./MeHistoryItemView.tsx` so it can be re-exported and unit-tested
 * with a sync `params` object without tripping the Page-module check.
 *
 * The default export here is a thin adapter: Next hands `params` in
 * as a Promise (per its async-routing migration); we resolve it via
 * React's `use()` hook and forward the sync object to the view.
 *
 * AC mapping (ISSUE-066):
 *   AC1 → past reading → archived audio streams (test exercised on
 *         the view: probe → 200, audio element gets src set).
 *   AC2 → blob missing → "이 풀이는 더 이상 재생할 수 없습니다"
 *         (test: probe → 410, fallback rendered).
 *   AC3 → tap pause → audio stops (native browser behavior on the
 *         `<audio controls>` element).
 */

import { use } from 'react';

import { MeHistoryItemView } from './MeHistoryItemView';

export default function MeHistoryItemPage({ params }: { params: Promise<{ id: string }> }) {
  const resolved = use(params);
  return <MeHistoryItemView params={resolved} />;
}
