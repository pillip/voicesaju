"use client";

/**
 * Client island for `/error/payment-failed` (ISSUE-075).
 *
 * Renders the visual chrome + wires the retry/navigate CTAs. Split out
 * so the sibling `page.tsx` can stay a Server Component (the Next.js 15
 * page-export contract our other surfaces follow — see /me/billing).
 *
 * State machine: this is a leaf screen with no async work; we just need
 * `router` for the two CTAs.
 */

import { useRouter } from "next/navigation";

import {
  CharacterIllustration,
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui";

export function PaymentFailedClient() {
  const router = useRouter();

  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-s4 bg-ink-900 px-s4 py-s8 text-cream-50"
      data-testid="payment-failed"
    >
      <div role="alert" aria-live="assertive" className="sr-only">
        결제가 실패했습니다. 다시 시도해주세요.
      </div>
      <CharacterIllustration
        character="nuna"
        data-testid="payment-failed-persona"
      />
      <h1 className="font-display text-2xl">결제가 안 됐네.</h1>
      <p className="max-w-sm text-center font-body text-sm text-cream-50/80">
        결제 처리 중 오류가 발생했어. 다시 시도해줘.
      </p>
      <div className="flex flex-col gap-s2 sm:flex-row">
        <PrimaryButton
          onClick={() => router.back()}
          data-testid="payment-failed-retry"
          aria-label="다시 시도"
        >
          다시 시도
        </PrimaryButton>
        <SecondaryButton
          onClick={() => router.push("/me")}
          data-testid="payment-failed-my"
          aria-label="마이페이지로"
        >
          마이페이지로
        </SecondaryButton>
      </div>
    </main>
  );
}
