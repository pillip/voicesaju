/**
 * `/legal/terms` — Terms of Service (ISSUE-074, FR-036, AC1).
 *
 * Static page; rendered as a Server Component (no `'use client'`) so
 * the HTML ships pre-rendered for fastest first paint and zero JS for
 * the legal copy itself. The shared chrome (TopAppBar) is a Client
 * Component, but Next.js 15 happily lets us mount it inside a server
 * page.
 *
 * AC checklist (FR-036 AC1):
 *   - Includes the "오락 목적" disclaimer so users understand voicesaju
 *     is entertainment, not professional advice.
 *   - Mentions third-party data processors (Toss Payments + Kakao OAuth)
 *     so the consent surface is auditable.
 *   - Renders inside the shared LegalShell so the back navigation +
 *     visual chrome match /legal/privacy and /legal/refund.
 *
 * Copy is intentionally placeholder boilerplate sized for v1 launch.
 * The legal review pass before launch will replace the body with the
 * counsel-approved version; the structure (sections + headings + key
 * disclaimers) is what NFR-005 audits.
 */

import { LegalShell } from "../LegalShell";

export const metadata = {
  title: "이용약관 | 보이스사주",
  description: "보이스사주 서비스 이용약관입니다.",
};

export default function TermsPage() {
  return (
    <LegalShell
      title="이용약관"
      headingId="legal-terms-title"
      updatedAt="2026-06-01"
    >
      <section aria-labelledby="terms-section-1">
        <h2
          id="terms-section-1"
          className="font-display text-base text-cream-50"
        >
          제1조 (목적)
        </h2>
        <p>
          본 약관은 보이스사주(이하 &ldquo;서비스&rdquo;)가 제공하는 음성
          사주풀이 콘텐츠 서비스의 이용 조건 및 절차, 회원과 서비스 제공자의
          권리·의무·책임 사항을 규정함을 목적으로 합니다.
        </p>
      </section>

      <section aria-labelledby="terms-section-2">
        <h2
          id="terms-section-2"
          className="font-display text-base text-cream-50"
        >
          제2조 (서비스의 성격 및 오락 목적 안내)
        </h2>
        <p>
          보이스사주는 <strong>오락 목적</strong>의 콘텐츠 서비스입니다. 본
          서비스에서 제공하는 사주풀이·타로 결과는 통계·전통 해석에 기반한
          참고용 텍스트와 음성으로, 의학적·법률적· 재무적 판단의 근거가 될 수
          없으며, 전문가의 자문을 대체하지 않습니다.
        </p>
        <p>
          이용자는 본 서비스의 콘텐츠를 <strong>오락 목적</strong>으로만
          활용해야 하며, 이를 근거로 한 의사결정에 대한 책임은 이용자 본인에게
          있습니다.
        </p>
      </section>

      <section aria-labelledby="terms-section-3">
        <h2
          id="terms-section-3"
          className="font-display text-base text-cream-50"
        >
          제3조 (회원가입 및 계정)
        </h2>
        <p>
          서비스는 카카오 OAuth를 통한 로그인을 지원합니다. 이용자는 카카오
          계정을 통해 서비스에 가입할 수 있으며, 가입 시 제공되는 정보는{" "}
          <a href="/legal/privacy" className="underline underline-offset-4">
            개인정보처리방침
          </a>
          에 따라 처리됩니다.
        </p>
      </section>

      <section aria-labelledby="terms-section-4">
        <h2
          id="terms-section-4"
          className="font-display text-base text-cream-50"
        >
          제4조 (유료 서비스 및 결제)
        </h2>
        <p>
          유료 풀이 및 구독 결제는 토스페이먼츠(Toss Payments)를 통해
          처리됩니다. 결제 정보는 토스페이먼츠 정책에 따라 저장·처리되며,
          서비스는 결제 카드 번호 등 민감한 결제 정보를 직접 보관하지 않습니다.
        </p>
        <p>
          환불 정책은{" "}
          <a href="/legal/refund" className="underline underline-offset-4">
            환불 정책
          </a>
          을 참조하세요.
        </p>
      </section>

      <section aria-labelledby="terms-section-5">
        <h2
          id="terms-section-5"
          className="font-display text-base text-cream-50"
        >
          제5조 (책임의 제한)
        </h2>
        <p>
          서비스는 천재지변, 외부 시스템 장애(LLM·TTS·결제 등), 이용자의 귀책
          사유로 인한 서비스 중단·오류에 대해 책임을 지지 않습니다. 단, LLM 또는
          TTS 장애로 결제된 풀이가 정상 제공되지 않은 경우 자동 환불 또는 무료
          이용권으로 보상합니다(자세한 내용은 환불 정책 참조).
        </p>
      </section>

      <section aria-labelledby="terms-section-6">
        <h2
          id="terms-section-6"
          className="font-display text-base text-cream-50"
        >
          제6조 (약관의 변경)
        </h2>
        <p>
          서비스는 관련 법령을 위배하지 않는 범위에서 본 약관을 변경할 수
          있으며, 변경된 약관은 서비스 내 공지 후 7일이 경과한 시점부터 효력이
          발생합니다.
        </p>
      </section>
    </LegalShell>
  );
}
