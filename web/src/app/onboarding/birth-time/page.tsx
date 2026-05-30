"use client";

/**
 * `/onboarding/birth-time` — Screen 3 (ISSUE-028).
 *
 * AC coverage:
 *   - AC2: "시간은 모르겠어요" check → spinners disable + birth_time_unknown=true.
 *   - AC3: back tap → return to /onboarding/birth-date with date preserved
 *     (handled implicitly by OnboardingChrome.back → router.back() and the
 *     Zustand store never clearing the birthDate).
 *
 * Why two number inputs rather than a single text "HH:MM":
 *   - Native step controls (inputMode=numeric + min/max) keep the validator
 *     simple — the validator only needs to check for nulls and ranges.
 *   - Keyboard nav is more predictable (Tab moves hour → minute → checkbox).
 */

import { useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { OnboardingChrome } from "@/components/onboarding/OnboardingChrome";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { validateBirthTime } from "@/lib/validators/onboarding";

export default function BirthTimePage() {
  const router = useRouter();
  const storeHour = useOnboardingStore((s) => s.birthHour);
  const storeMinute = useOnboardingStore((s) => s.birthMinute);
  const storeUnknown = useOnboardingStore((s) => s.birthTimeUnknown);
  const setBirthHour = useOnboardingStore((s) => s.setBirthHour);
  const setBirthMinute = useOnboardingStore((s) => s.setBirthMinute);
  const setBirthTimeUnknown = useOnboardingStore((s) => s.setBirthTimeUnknown);

  const [hour, setHour] = useState<string>(
    storeHour === null ? "" : String(storeHour),
  );
  const [minute, setMinute] = useState<string>(
    storeMinute === null ? "" : String(storeMinute),
  );

  // Re-sync from store on mount / when the store changes (back-nav contract).
  useEffect(() => {
    setHour(storeHour === null ? "" : String(storeHour));
    setMinute(storeMinute === null ? "" : String(storeMinute));
  }, [storeHour, storeMinute]);

  const hourId = useId();
  const minuteId = useId();
  const checkboxId = useId();

  const parsedHour = hour === "" ? null : Number(hour);
  const parsedMinute = minute === "" ? null : Number(minute);
  const validationCode = validateBirthTime({
    hour: parsedHour,
    minute: parsedMinute,
    unknown: storeUnknown,
  });
  const canProceed = validationCode === null;

  function handleUnknownChange(next: boolean) {
    setBirthTimeUnknown(next);
    if (next) {
      setHour("");
      setMinute("");
    }
  }

  function handleNext() {
    if (!canProceed) return;
    if (!storeUnknown) {
      setBirthHour(parsedHour);
      setBirthMinute(parsedMinute);
    }
    router.push("/onboarding/gender");
  }

  return (
    <OnboardingChrome step={2}>
      <div className="flex flex-col gap-s2">
        <h1 className="font-display-han text-2xl text-cream-50">태어난 시각</h1>
        <p className="font-body text-base text-cream-300">몇 시쯤이었어?</p>
      </div>

      <div className="flex items-end gap-s3">
        <div className="flex-1">
          <label
            htmlFor={hourId}
            className="block font-body text-sm text-cream-300"
          >
            시
          </label>
          <input
            id={hourId}
            type="number"
            inputMode="numeric"
            min={0}
            max={23}
            placeholder="14"
            value={hour}
            disabled={storeUnknown}
            onChange={(e) => setHour(e.target.value)}
            className="mt-s1 w-full rounded-md border border-cream-600 bg-ink-800 px-s4 py-s3 font-body text-base text-cream-50 placeholder:text-cream-400 focus-visible:border-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300 disabled:opacity-50"
          />
        </div>
        <span className="pb-s4 font-display text-cream-300">:</span>
        <div className="flex-1">
          <label
            htmlFor={minuteId}
            className="block font-body text-sm text-cream-300"
          >
            분
          </label>
          <input
            id={minuteId}
            type="number"
            inputMode="numeric"
            min={0}
            max={59}
            placeholder="30"
            value={minute}
            disabled={storeUnknown}
            onChange={(e) => setMinute(e.target.value)}
            className="mt-s1 w-full rounded-md border border-cream-600 bg-ink-800 px-s4 py-s3 font-body text-base text-cream-50 placeholder:text-cream-400 focus-visible:border-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300 disabled:opacity-50"
          />
        </div>
      </div>

      <div className="flex items-start gap-s2">
        <input
          id={checkboxId}
          type="checkbox"
          checked={storeUnknown}
          onChange={(e) => handleUnknownChange(e.target.checked)}
          className="mt-1 h-5 w-5 cursor-pointer rounded border-cream-600 bg-ink-800 text-amber-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
        />
        <label
          htmlFor={checkboxId}
          className="cursor-pointer font-body text-base text-cream-100"
        >
          시간은 모르겠어요
        </label>
      </div>

      {storeUnknown && (
        <p className="rounded-md border border-cream-600 bg-ink-800 p-s3 font-body text-sm text-cream-200">
          시간을 모르면 큰 줄기는 봐도 디테일은 조금 흐릿해. 괜찮아.
        </p>
      )}

      <div className="mt-auto flex flex-col gap-s3 pb-s4">
        <PrimaryButton
          type="button"
          onClick={handleNext}
          disabled={!canProceed}
          aria-label="다음"
          className="w-full"
        >
          다음
        </PrimaryButton>
      </div>
    </OnboardingChrome>
  );
}
