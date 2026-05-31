/**
 * `/error/llm-failed` — Screen 26 (ISSUE-075, FR-033, FR-035).
 *
 * Surface for the case where the LLM pipeline failed post-payment. The
 * reading row has been marked `status='failed'` and the backend has
 * enqueued the automatic refund worker (`refund_for_reading`, see
 * ISSUE-076). This screen tells the user "별기운이 잠시 약하네…" +
 * "환불 또는 무료 이용권이 지급되었어요" so they know they're not out
 * of pocket.
 *
 * Copy follows copy_guide §22 row "Error: LLM 실패" + Screen 26 spec
 * in ux_spec §745:
 *   - H1: "별기운이 잠시 약하네…"
 *   - Body: "환불 또는 무료 이용권이 지급되었어요"
 *   - CTA: "다시 시도" → /reading/category
 *   - Secondary CTA: "마이페이지로" → /me
 *
 * Server Component shell + client island for CTAs (Next.js 15 page-export
 * contract — same split as /error/payment-failed).
 */

import { LlmFailedClient } from "./LlmFailedClient";

export const metadata = {
  title: "풀이 실패 | 보이스사주",
};

export default function LlmFailedPage() {
  return <LlmFailedClient />;
}
