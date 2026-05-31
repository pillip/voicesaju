/**
 * `/legal/refund` — Refund Policy (ISSUE-074, FR-036, AC3).
 *
 * Static Server Component; same shell as the other legal pages.
 *
 * AC checklist (FR-036 AC3):
 *   - Documents the **자동 환불** path for LLM/TTS-failed paid readings
 *     (the FR-023 / FR-033 contract — see api/voicesaju/payment/refund.py
 *     for the implementation surface).
 *   - Documents the **무료 이용권 보상** fallback when the upstream
 *     refund call to Toss fails (kind='failure_compensation' token).
 *   - States the 7-day general refund window for paid readings that
 *     have not been delivered.
 *   - States the no-refund policy for subscription-derived readings
 *     once they've been generated (matches FR-021's billing contract).
 *
 * Copy is placeholder boilerplate sized for v1 launch; the legal review
 * pass replaces the body before production.
 */

import { LegalShell } from "../LegalShell";

export const metadata = {
  title: "환불 정책 | 보이스사주",
  description: "보이스사주 환불 정책입니다.",
};

export default function RefundPage() {
  return (
    <LegalShell
      title="환불 정책"
      headingId="legal-refund-title"
      updatedAt="2026-06-01"
    >
      <section aria-labelledby="refund-section-1">
        <h2
          id="refund-section-1"
          className="font-display text-base text-cream-50"
        >
          1. 단건 결제 환불
        </h2>
        <p>
          단건 풀이 결제 후 풀이 콘텐츠를 아직 수신하지 않은 경우, 결제일로부터
          7일 이내에 마이페이지 또는 고객 문의를 통해 전액 환불을 요청할 수
          있습니다.
        </p>
        <p>
          풀이 콘텐츠가 정상적으로 생성·전달된 이후의 자발적 환불은 콘텐츠
          특성상 제한될 수 있으며, 개별 사안에 대해 검토 후 처리됩니다.
        </p>
      </section>

      <section aria-labelledby="refund-section-2">
        <h2
          id="refund-section-2"
          className="font-display text-base text-cream-50"
        >
          2. LLM·TTS 장애 시 자동 환불
        </h2>
        <p>
          결제된 풀이가 외부 LLM(언어 모델) 또는 TTS(음성 합성) 장애로 인해 정상
          제공되지 못한 경우, 별도의 요청 없이 <strong>자동으로 환불</strong>
          됩니다. 결제 수단 환불이 정상 완료되면 환불 내역은 마이페이지에서
          확인할 수 있습니다.
        </p>
      </section>

      <section aria-labelledby="refund-section-3">
        <h2
          id="refund-section-3"
          className="font-display text-base text-cream-50"
        >
          3. 결제 수단 환불 실패 시 무료 이용권 보상
        </h2>
        <p>
          토스페이먼츠 등 결제 처리자 장애로 인해 결제 수단으로의 환불이 즉시
          처리되지 않을 경우, 동등 가치의 <strong>무료 이용권</strong>이 자동
          지급됩니다. 무료 이용권은 마이페이지에서 확인할 수 있으며, 다음 풀이에
          즉시 사용 가능합니다.
        </p>
        <p>
          무료 이용권은 결제 수단 환불의 대체 보상 수단이며, 이용자가 원할 경우
          고객 문의를 통해 결제 수단 환불로의 전환을 요청할 수 있습니다.
        </p>
      </section>

      <section aria-labelledby="refund-section-4">
        <h2
          id="refund-section-4"
          className="font-display text-base text-cream-50"
        >
          4. 월 구독 결제 환불
        </h2>
        <p>
          월 구독은 결제일로부터 7일 이내, 구독 혜택을 한 번도 사용하지 않은
          경우에 한해 전액 환불이 가능합니다. 구독 기간 중 한 건이라도 풀이를
          이용한 경우 부분 환불은 제공되지 않으며, 다음 결제일까지 서비스를
          이용할 수 있습니다.
        </p>
        <p>
          구독 해지는 마이페이지에서 즉시 처리되며, 해지 이후에는 다음 결제일에
          자동 결제가 이루어지지 않습니다.
        </p>
      </section>

      <section aria-labelledby="refund-section-5">
        <h2
          id="refund-section-5"
          className="font-display text-base text-cream-50"
        >
          5. 환불 처리 기간
        </h2>
        <p>
          환불 요청이 승인된 경우 영업일 기준 3~5일 이내에 결제 수단으로
          환불됩니다. 카드사·은행 사정에 따라 실제 입금까지 추가 시일이 소요될
          수 있습니다.
        </p>
      </section>

      <section aria-labelledby="refund-section-6">
        <h2
          id="refund-section-6"
          className="font-display text-base text-cream-50"
        >
          6. 문의
        </h2>
        <p>
          환불 관련 문의는 아래 채널로 연락 주세요.
          <br />
          이메일: support@voicesaju.app
        </p>
      </section>
    </LegalShell>
  );
}
