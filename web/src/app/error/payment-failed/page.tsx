/**
 * `/error/payment-failed` — Toss payment failure screen (ISSUE-075).
 *
 * Surface for the case where the Toss SDK modal returns an error code
 * (e.g. card declined, network drop mid-confirm). The user lands here
 * via `router.push('/error/payment-failed?reason=...')` from the
 * checkout route's error handler.
 *
 * Copy follows copy_guide §28 row "Error: 일반 결제 실패":
 *   - H1: "결제가 안 됐네."
 *   - Body: "다시 시도해줘." (with optional reason context)
 *   - CTA: "다시 시도" → router.back() to the paywall.
 *   - Secondary CTA: "마이페이지로" → /me.
 *
 * Server-rendered for fast paint; the retry CTA is a client island
 * because it needs `router.back()`. We split the client portion into
 * a sibling module so the page export stays a Server Component (matches
 * the Next.js 15 page-export contract used elsewhere in the app).
 */

import { PaymentFailedClient } from "./PaymentFailedClient";

export const metadata = {
  title: "결제 실패 | 보이스사주",
};

export default function PaymentFailedPage() {
  return <PaymentFailedClient />;
}
