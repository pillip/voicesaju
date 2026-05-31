/**
 * `/upsell/subscription` — Screen 22 (ISSUE-070): route entry point.
 *
 * Next 15 forbids any named exports from a `page.tsx` other than the
 * small allowlist of route-config symbols. The view + its test
 * surface live in `./UpsellSubscriptionView.tsx`; this module is a
 * thin default-export wrapper so the build's Page-module check
 * passes.
 *
 * Same Page-module-export pattern as /me/billing (ISSUE-067),
 * /me/billing/subscribe (ISSUE-069), /me/history (ISSUE-065), and
 * /me/edit-saju (ISSUE-071).
 */

import { UpsellSubscriptionView } from './UpsellSubscriptionView';

export default function UpsellSubscriptionPage() {
  return <UpsellSubscriptionView />;
}
