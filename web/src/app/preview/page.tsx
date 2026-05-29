/**
 * Design system preview (/preview) — ISSUE-021.
 *
 * Renders every base UI component in its default / disabled / loading state so
 * designers and engineers can eyeball the v1 token system end-to-end. axe-core
 * scans this page in `src/app/preview/__tests__/a11y.test.tsx` to enforce
 * zero WCAG 2.1 AA violations.
 */
import {
  Banner,
  CategoryCard,
  OptionCard,
  PrimaryButton,
  SecondaryButton,
  StepIndicator,
  TertiaryLink,
  Toast,
} from "@/components/ui";
import { NavChromePreview } from "./NavChromePreview";

type State = "default" | "disabled" | "loading";

function Row({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-labelledby={`section-${title}`}
      className="flex flex-col gap-s4 border-b border-ink-600 py-s6"
    >
      <header className="flex flex-col gap-s2">
        <h2
          id={`section-${title}`}
          className="font-display text-2xl text-cream-50"
        >
          {title}
        </h2>
        {description && <p className="text-sm text-cream-300">{description}</p>}
      </header>
      <div className="grid grid-cols-1 gap-s4 md:grid-cols-3">{children}</div>
    </section>
  );
}

function StateCell({
  state,
  children,
}: {
  state: State;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-s2">
      <span className="font-mono text-xs uppercase tracking-wider text-cream-400">
        {state}
      </span>
      {children}
    </div>
  );
}

export default function PreviewPage() {
  return (
    <main
      id="preview"
      className="mx-auto flex max-w-5xl flex-col gap-s8 bg-ink-900 px-s6 py-s10 text-cream-100"
    >
      <header className="flex flex-col gap-s2">
        <h1 className="font-display text-4xl text-cream-50">
          VoiceSaju 디자인 시스템 v1
        </h1>
        <p className="text-sm text-cream-300">
          ISSUE-021 미리보기 — 기본 컴포넌트 8종 × 3개 상태 (default / disabled
          / loading).
        </p>
      </header>

      <Row title="PrimaryButton">
        <StateCell state="default">
          <PrimaryButton data-testid="preview-PrimaryButton-default">
            저장하기
          </PrimaryButton>
        </StateCell>
        <StateCell state="disabled">
          <PrimaryButton disabled data-testid="preview-PrimaryButton-disabled">
            저장하기
          </PrimaryButton>
        </StateCell>
        <StateCell state="loading">
          <PrimaryButton loading data-testid="preview-PrimaryButton-loading">
            저장하기
          </PrimaryButton>
        </StateCell>
      </Row>

      <Row title="SecondaryButton">
        <StateCell state="default">
          <SecondaryButton data-testid="preview-SecondaryButton-default">
            취소
          </SecondaryButton>
        </StateCell>
        <StateCell state="disabled">
          <SecondaryButton
            disabled
            data-testid="preview-SecondaryButton-disabled"
          >
            취소
          </SecondaryButton>
        </StateCell>
        <StateCell state="loading">
          <SecondaryButton
            loading
            data-testid="preview-SecondaryButton-loading"
          >
            취소
          </SecondaryButton>
        </StateCell>
      </Row>

      <Row title="TertiaryLink">
        <StateCell state="default">
          <TertiaryLink
            href="#terms"
            data-testid="preview-TertiaryLink-default"
          >
            이용 약관 보기
          </TertiaryLink>
        </StateCell>
        <StateCell state="disabled">
          <TertiaryLink
            href="#terms"
            disabled
            data-testid="preview-TertiaryLink-disabled"
          >
            이용 약관 보기
          </TertiaryLink>
        </StateCell>
        <StateCell state="loading">
          {/* TertiaryLink has no native loading; we expose a disabled+busy hint */}
          <TertiaryLink
            href="#terms"
            aria-busy="true"
            data-testid="preview-TertiaryLink-loading"
          >
            이용 약관 보기
          </TertiaryLink>
        </StateCell>
      </Row>

      <Row title="CategoryCard" description="연애 / 직장 / 금전 / 타로">
        <StateCell state="default">
          <CategoryCard
            category="love"
            data-testid="preview-CategoryCard-default"
          >
            연애운 상세
          </CategoryCard>
        </StateCell>
        <StateCell state="disabled">
          <CategoryCard
            category="work"
            disabled
            data-testid="preview-CategoryCard-disabled"
          >
            직장운 잠금
          </CategoryCard>
        </StateCell>
        <StateCell state="loading">
          <CategoryCard
            category="money"
            loading
            data-testid="preview-CategoryCard-loading"
          >
            금전운 불러오는 중
          </CategoryCard>
        </StateCell>
      </Row>

      <Row title="OptionCard">
        <StateCell state="default">
          <OptionCard data-testid="preview-OptionCard-default">여성</OptionCard>
        </StateCell>
        <StateCell state="disabled">
          <OptionCard disabled data-testid="preview-OptionCard-disabled">
            여성
          </OptionCard>
        </StateCell>
        <StateCell state="loading">
          <OptionCard loading data-testid="preview-OptionCard-loading">
            여성
          </OptionCard>
        </StateCell>
      </Row>

      <Row title="StepIndicator">
        <StateCell state="default">
          <div data-testid="preview-StepIndicator-default">
            <StepIndicator total={3} current={2} />
          </div>
        </StateCell>
        <StateCell state="disabled">
          {/* Disabled rendered as a fully-completed indicator */}
          <div data-testid="preview-StepIndicator-disabled">
            <StepIndicator total={3} current={3} />
          </div>
        </StateCell>
        <StateCell state="loading">
          <div data-testid="preview-StepIndicator-loading">
            <StepIndicator total={3} current={1} loading />
          </div>
        </StateCell>
      </Row>

      <Row title="Toast">
        <StateCell state="default">
          <div data-testid="preview-Toast-default">
            <Toast tone="success">저장되었습니다</Toast>
          </div>
        </StateCell>
        <StateCell state="disabled">
          {/* Toast has no native disabled — we render a muted info tone */}
          <div data-testid="preview-Toast-disabled">
            <Toast tone="info">알림이 비활성화되었습니다</Toast>
          </div>
        </StateCell>
        <StateCell state="loading">
          <div data-testid="preview-Toast-loading">
            <Toast tone="info" loading>
              업로드 중...
            </Toast>
          </div>
        </StateCell>
      </Row>

      <NavChromePreview />

      <Row title="Banner">
        <StateCell state="default">
          <div data-testid="preview-Banner-default">
            <Banner tone="info">새 기능이 추가되었습니다.</Banner>
          </div>
        </StateCell>
        <StateCell state="disabled">
          <div data-testid="preview-Banner-disabled">
            <Banner tone="warning" disabled>
              이전 알림입니다.
            </Banner>
          </div>
        </StateCell>
        <StateCell state="loading">
          {/* Banner has no native loading — render the error tone */}
          <div data-testid="preview-Banner-loading">
            <Banner tone="error">결제에 실패했습니다.</Banner>
          </div>
        </StateCell>
      </Row>
    </main>
  );
}
