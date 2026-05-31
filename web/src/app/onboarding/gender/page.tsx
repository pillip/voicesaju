'use client';

/**
 * `/onboarding/gender` — Screen 4 (ISSUE-028).
 *
 * Behaviour:
 *   - Two OptionCard radios (여자 / 남자) — tap auto-advances to /onboarding/name.
 *   - Selected value persists in the Zustand store so back-nav re-renders
 *     with aria-checked set on the previously-chosen option.
 *   - Back button → router.back() via OnboardingChrome.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { OnboardingChrome } from '@/components/onboarding/OnboardingChrome';
import { trackOnboardingStep } from '@/lib/analytics/events';
import { useOnboardingStore } from '@/lib/stores/onboarding-store';
import type { Gender } from '@/lib/stores/onboarding-store';
import { cn } from '@/lib/utils';

export default function GenderPage() {
  const router = useRouter();
  const gender = useOnboardingStore((s) => s.gender);
  const setGender = useOnboardingStore((s) => s.setGender);

  // ISSUE-080 AC1: fire ``onboarding_step`` once per visit (step 3 of 4).
  useEffect(() => {
    trackOnboardingStep(3);
  }, []);

  function handleSelect(g: Gender) {
    setGender(g);
    // Auto-advance per Screen 4 spec — no explicit 다음 button.
    router.push('/onboarding/name');
  }

  return (
    <OnboardingChrome step={3}>
      <div className="flex flex-col gap-s2">
        <h1 className="font-display-han text-2xl text-cream-50">성별</h1>
        <p className="font-body text-base text-cream-300">짧게.</p>
      </div>

      <div role="radiogroup" aria-label="성별 선택" className="flex flex-col gap-s3">
        <GenderCard
          label="여자"
          selected={gender === 'female'}
          onClick={() => handleSelect('female')}
        />
        <GenderCard
          label="남자"
          selected={gender === 'male'}
          onClick={() => handleSelect('male')}
        />
      </div>

      <p className="mt-auto pb-s4 text-center font-body text-xs text-cream-400">
        사주 명식 계산에만 사용돼요.
      </p>
    </OnboardingChrome>
  );
}

interface GenderCardProps {
  label: '여자' | '남자';
  selected: boolean;
  onClick: () => void;
}

/**
 * Tappable card option styled like OptionCard but larger (Screen 4 spec —
 * "two large tappable cards"). Inline to avoid bloating the global UI primitives
 * for a one-off shape.
 */
function GenderCard({ label, selected, onClick }: GenderCardProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={cn(
        'flex h-[120px] w-full items-center justify-center rounded-md border font-display text-3xl transition-colors',
        selected
          ? 'border-amber-400 bg-ink-700 text-cream-50'
          : 'border-cream-600 bg-ink-800 text-cream-200 hover:border-cream-300',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
      )}
    >
      {label}
    </button>
  );
}
