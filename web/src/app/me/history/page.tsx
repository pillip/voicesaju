/**
 * `/me/history` — Screen 18 (ISSUE-065): reading history list.
 *
 * Next 15 forbids any named exports from a `page.tsx` other than the
 * small allowlist of route-config symbols. The view + its test
 * surface live in `./HistoryListView.tsx`; this module is a thin
 * default-export wrapper so the build's Page-module check passes.
 *
 * Why this split exists at all:
 *  - The lesson from ISSUE-066 + ISSUE-071 is that `page.tsx` cannot
 *    export `interface FooProps {}` (typescript named export) without
 *    triggering the Next build's "Page must only export ..." error.
 *  - Tests still want a sync, prop-injectable component to render
 *    under jsdom — so they import the view directly.
 */

import { HistoryListView } from "./HistoryListView";

export default function MeHistoryPage() {
  return <HistoryListView />;
}
