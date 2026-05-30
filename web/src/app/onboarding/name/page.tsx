"use client";

/**
 * `/onboarding/name` — Screen 5 (ISSUE-028).
 *
 * AC coverage:
 *   - AC4: name > 10 chars → inline error "이름은 10자 이내로 적어줘".
 *
 * Behaviour notes:
 *   - The primary CTA flips between "완료" (with a name) and "이름 없이 계속하기"
 *     (empty input — Screen 5 empty state).
 *   - "건너뛰기" routes to /reading/category without persisting the name.
 *   - Profile API call is out of scope (handled by ISSUE-029).
 */

import { useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { SecondaryButton } from "@/components/ui/SecondaryButton";
import { OnboardingChrome } from "@/components/onboarding/OnboardingChrome";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { NAME_TOO_LONG_COPY, validateName } from "@/lib/validators/onboarding";

export default function NamePage() {
  const router = useRouter();
  const storeName = useOnboardingStore((s) => s.name);
  const setStoreName = useOnboardingStore((s) => s.setName);

  const [value, setValue] = useState(storeName);

  useEffect(() => {
    setValue(storeName);
  }, [storeName]);

  const inputId = useId();
  const errorId = useId();
  const errorCode = validateName(value);
  const errorMsg = errorCode === "too-long" ? NAME_TOO_LONG_COPY : null;
  const canSubmit = errorCode === null;
  const trimmed = value.trim();

  const primaryLabel = trimmed.length === 0 ? "이름 없이 계속하기" : "완료";

  function handleSubmit() {
    if (!canSubmit) return;
    setStoreName(trimmed);
    router.push("/reading/category");
  }

  function handleSkip() {
    setStoreName("");
    router.push("/reading/category");
  }

  return (
    <OnboardingChrome step={4}>
      <div className="flex flex-col gap-s2">
        <h1 className="font-display-han text-2xl text-cream-50">이름</h1>
        <p className="font-body text-base text-cream-300">
          부를 때 쓸게. 안 적어도 돼.
        </p>
      </div>

      <div className="flex flex-col gap-s3">
        <label htmlFor={inputId} className="font-body text-sm text-cream-300">
          이름 (옵셔널)
        </label>
        <input
          id={inputId}
          type="text"
          autoComplete="given-name"
          placeholder="효주"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={errorCode !== null}
          aria-describedby={errorMsg ? errorId : undefined}
          className="w-full rounded-md border border-cream-600 bg-ink-800 px-s4 py-s3 font-body text-base text-cream-50 placeholder:text-cream-400 focus-visible:border-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
        />
        {errorMsg && (
          <p
            id={errorId}
            role="alert"
            className="font-body text-sm text-state-error"
            data-testid="name-error"
          >
            {errorMsg}
          </p>
        )}
      </div>

      <div className="mt-auto flex flex-col gap-s3 pb-s4">
        <PrimaryButton
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          aria-label={primaryLabel}
          className="w-full"
        >
          {primaryLabel}
        </PrimaryButton>
        <SecondaryButton
          type="button"
          onClick={handleSkip}
          aria-label="건너뛰기"
          className="w-full"
        >
          건너뛰기
        </SecondaryButton>
      </div>
    </OnboardingChrome>
  );
}
