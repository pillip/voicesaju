"use client";

/**
 * Client island for `/error/llm-failed` (ISSUE-075, Screen 26).
 *
 * Visual contract mirrors the inline ErrorShell in
 * `/reading/play` (PlayClient.tsx). We don't share the component
 * because PlayClient.ErrorShell is wired to its parent's local state
 * machine (retry resets the chunk stream); this standalone route is
 * routed-in, so the retry CTA navigates back to `/reading/category`
 * instead of resetting in-place.
 */

import { useRouter } from "next/navigation";

import {
  CharacterIllustration,
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui";

const H1_COPY = "별기운이 잠시 약하네…";
const BODY_COPY = "환불 또는 무료 이용권이 지급되었어요";

export function LlmFailedClient() {
  const router = useRouter();

  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 px-s4 py-s8 text-cream-50"
      data-testid="llm-failed"
    >
      <div role="alert" aria-live="assertive" className="sr-only">
        풀이 생성에 실패했어요. 환불 또는 무료 이용권이 지급되었습니다.
      </div>
      <CharacterIllustration
        character="nuna"
        data-testid="llm-failed-persona"
      />
      <h1 className="font-display text-2xl" data-testid="llm-failed-title">
        {H1_COPY}
      </h1>
      <p
        className="max-w-sm text-center font-body text-sm text-cream-50/80"
        data-testid="llm-failed-body"
      >
        {BODY_COPY}
      </p>
      <div className="flex flex-col gap-s2 sm:flex-row">
        <PrimaryButton
          onClick={() => router.push("/reading/category")}
          data-testid="llm-failed-retry"
          aria-label="다시 시도"
        >
          다시 시도
        </PrimaryButton>
        <SecondaryButton
          onClick={() => router.push("/me")}
          data-testid="llm-failed-my"
          aria-label="마이페이지로"
        >
          마이페이지로
        </SecondaryButton>
      </div>
    </main>
  );
}
