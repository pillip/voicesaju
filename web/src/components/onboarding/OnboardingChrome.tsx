"use client";

/**
 * Shared chrome for all 4 onboarding pages (ISSUE-028).
 *
 * Wraps:
 *   - TopAppBar with a "뒤로" back button (router.back()) and a
 *     "STEP N/4" right-aligned label (copy_guide §2).
 *   - StepIndicator beneath the chrome.
 *   - A semantic <main> container for the step's content.
 *
 * The chrome itself is purely presentational — pages own all navigation logic
 * and form state. Keeping the chrome dumb makes it easy to unit-test each
 * step page in isolation (the chrome renders the same nodes regardless of
 * which page renders it).
 */

import { useRouter } from "next/navigation";
import { StepIndicator } from "@/components/ui/StepIndicator";
import { TopAppBar } from "@/components/nav/TopAppBar";

export interface OnboardingChromeProps {
  step: 1 | 2 | 3 | 4;
  children: React.ReactNode;
}

export function OnboardingChrome({ step, children }: OnboardingChromeProps) {
  const router = useRouter();
  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <TopAppBar
        back={
          <button
            type="button"
            aria-label="뒤로"
            onClick={() => router.back()}
            className="inline-flex h-[44px] w-[44px] items-center justify-center rounded-md text-cream-100 transition-colors hover:bg-ink-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          >
            ←
          </button>
        }
        action={
          <span
            className="font-body text-xs text-cream-300"
            aria-label={`스텝 ${step} / 4`}
            data-testid="step-meta"
          >
            STEP {step}/4
          </span>
        }
      />
      <div className="px-s4 pt-s4">
        <StepIndicator total={4} current={step} />
      </div>
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s6 px-s4 py-s8">
        {children}
      </main>
    </div>
  );
}
