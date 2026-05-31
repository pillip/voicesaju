/**
 * `/legal/privacy` — Privacy Policy (ISSUE-074, FR-036, AC2).
 *
 * Static Server Component; same shell as /legal/terms.
 *
 * AC checklist (FR-036 AC2):
 *   - Mentions AES-256 encryption of birth date / time at rest. The
 *     concrete pipeline is: app encrypts via the active KMS provider
 *     (LOCAL_KEK_BASE64 in Phase-1, AWS KMS in Phase-2), persists
 *     ciphertext in `user_profiles.birth_*_encrypted` columns. See
 *     architecture §7.3 for the data-flow diagram.
 *   - Mentions Toss Payments as a personal-information processor and
 *     links out to their privacy policy.
 *   - Lists retention periods + the deletion path (account close).
 *   - Includes a Data Protection Officer contact channel.
 *
 * Copy is placeholder boilerplate sized for v1 launch; the legal review
 * pass replaces the body before production.
 */

import { LegalShell } from "../LegalShell";

export const metadata = {
  title: "개인정보처리방침 | 보이스사주",
  description: "보이스사주 개인정보처리방침입니다.",
};

export default function PrivacyPage() {
  return (
    <LegalShell
      title="개인정보처리방침"
      headingId="legal-privacy-title"
      updatedAt="2026-06-01"
    >
      <section aria-labelledby="privacy-section-1">
        <h2
          id="privacy-section-1"
          className="font-display text-base text-cream-50"
        >
          1. 수집하는 개인정보 항목
        </h2>
        <p>보이스사주는 서비스 제공을 위해 다음의 개인정보를 수집합니다.</p>
        <ul className="list-disc space-y-s1 pl-s4">
          <li>
            회원가입 시(카카오 OAuth): 카카오 회원번호, 닉네임, 이메일(선택).
          </li>
          <li>
            사주풀이 이용 시: 이름(별명 가능), 생년월일, 출생 시각(선택), 성별.
          </li>
          <li>
            결제 시: 결제 수단·금액·결제 일시(결제 카드 번호 등 민감 정보는
            토스페이먼츠가 직접 처리).
          </li>
          <li>자동 수집: 접속 로그, 기기 정보, 쿠키, IP.</li>
        </ul>
      </section>

      <section aria-labelledby="privacy-section-2">
        <h2
          id="privacy-section-2"
          className="font-display text-base text-cream-50"
        >
          2. 수집 목적
        </h2>
        <ul className="list-disc space-y-s1 pl-s4">
          <li>사주풀이 결과 생성 및 음성 합성 콘텐츠 제공.</li>
          <li>회원 식별, 부정 이용 방지, 고객 문의 응대.</li>
          <li>결제 처리 및 환불 정산.</li>
          <li>
            서비스 품질 개선을 위한 통계 분석(개인 식별 정보 비결합 형태).
          </li>
        </ul>
      </section>

      <section aria-labelledby="privacy-section-3">
        <h2
          id="privacy-section-3"
          className="font-display text-base text-cream-50"
        >
          3. 민감 정보의 암호화 보관
        </h2>
        <p>
          이용자의 생년월일·출생 시각 등 사주풀이 핵심 입력값은{" "}
          <strong>AES-256</strong> 알고리즘으로 암호화하여 저장합니다. 암호 키는
          별도의 키 관리 시스템(KMS)에서 분리 보관하며, 서비스 운영자가 평문
          상태로 접근할 수 없는 구조입니다.
        </p>
      </section>

      <section aria-labelledby="privacy-section-4">
        <h2
          id="privacy-section-4"
          className="font-display text-base text-cream-50"
        >
          4. 개인정보의 제3자 처리위탁
        </h2>
        <p>
          서비스는 결제 처리 및 인증을 위해 아래 처리자에게 일부 정보를
          위탁합니다.
        </p>
        <ul className="list-disc space-y-s1 pl-s4">
          <li>
            <strong>토스페이먼츠(Toss Payments)</strong> — 결제 승인·취소·환불
            처리. 결제 카드 번호 등 결제 정보는 토스페이먼츠가 자체
            보관·처리합니다.{" "}
            <a
              href="https://docs.tosspayments.com/resources/privacy"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4"
            >
              토스페이먼츠 개인정보처리방침
            </a>
            을 참조하세요.
          </li>
          <li>
            <strong>카카오</strong> — OAuth 로그인 인증 토큰 발급.
          </li>
        </ul>
      </section>

      <section aria-labelledby="privacy-section-5">
        <h2
          id="privacy-section-5"
          className="font-display text-base text-cream-50"
        >
          5. 보유 기간 및 파기
        </h2>
        <p>
          회원 정보는 회원 탈퇴 시 즉시 파기합니다. 단, 관련 법령(전자상거래법,
          통신비밀 보호법)에 따라 다음 항목은 일정 기간 보관 후 파기합니다.
        </p>
        <ul className="list-disc space-y-s1 pl-s4">
          <li>결제·환불·계약 관련 기록: 5년.</li>
          <li>접속 로그: 3개월.</li>
        </ul>
      </section>

      <section aria-labelledby="privacy-section-6">
        <h2
          id="privacy-section-6"
          className="font-display text-base text-cream-50"
        >
          6. 이용자의 권리
        </h2>
        <p>
          이용자는 언제든지 본인의 개인정보 열람, 정정, 삭제, 처리정지를 요청할
          수 있습니다. 또한 마이페이지에서 직접 계정 탈퇴를 진행할 수 있으며,
          탈퇴 시 모든 개인정보는 즉시 파기됩니다.
        </p>
      </section>

      <section aria-labelledby="privacy-section-7">
        <h2
          id="privacy-section-7"
          className="font-display text-base text-cream-50"
        >
          7. 개인정보 보호책임자
        </h2>
        <p>
          개인정보 보호 관련 문의는 아래 채널로 연락 주세요.
          <br />
          이메일: privacy@voicesaju.app
        </p>
      </section>
    </LegalShell>
  );
}
