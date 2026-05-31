/**
 * `/me/billing` — Screen 20 (ISSUE-067): route entry point.
 *
 * Next 15 forbids any named exports from a `page.tsx` other than the
 * small allowlist of route-config symbols. The view + its test
 * surface live in `./BillingView.tsx`; this module is a thin
 * default-export wrapper so the build's Page-module check passes.
 *
 * Same Page-module-export pattern as /me/history (ISSUE-065) and
 * /me/edit-saju (ISSUE-071).
 */

import { BillingView } from "./BillingView";

export default function MeBillingPage() {
  return <BillingView />;
}
