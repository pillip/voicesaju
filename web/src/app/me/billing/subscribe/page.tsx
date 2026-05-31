/**
 * `/me/billing/subscribe` — Subscription checkout flow (ISSUE-069).
 *
 * Next 15 forbids any named exports from a `page.tsx` other than the
 * small allowlist of route-config symbols, so the view + its test
 * surface live in `./SubscribeView.tsx` and this module is a thin
 * default-export wrapper.
 *
 * Same Page-module-export pattern as /me/billing (ISSUE-067),
 * /me/history (ISSUE-065), and /me/edit-saju (ISSUE-071).
 */

import { SubscribeView } from './SubscribeView';

export default function MeBillingSubscribePage() {
  return <SubscribeView />;
}
