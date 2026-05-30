"use client";

/**
 * `/onboarding/birth-date` — Screen 2 of `docs/ux_spec.md` (ISSUE-028).
 *
 * AC coverage:
 *   - AC1: valid solar date + tap 다음 → router pushes /onboarding/birth-time,
 *     date persisted to the Zustand store.
 *   - AC5: keyboard tab order — date input → calendar toggle → 다음 button.
 *
 * Why native `<input type="date">` rather than react-day-picker:
 *   - Zero dependencies; the issue's Scope Management Guidance asks for the
 *     thinnest possible primitive. The actual visual calendar opens via the
 *     native picker, which is consistent with Toss WebView (no popover
 *     conflict).
 *   - Validation is purely string-level (YYYY-MM-DD), which matches the
 *     `validateBirthDate` contract in `src/lib/validators/onboarding.ts`.
 */

import { useId, useMemo, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { OnboardingChrome } from "@/components/onboarding/OnboardingChrome";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import {
  birthDateErrorCopy,
  validateBirthDate,
  type BirthDateError,
} from "@/lib/validators/onboarding";

function todayIso(): string {
  // YYYY-MM-DD in local time. Matches what a native date input emits.
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export default function BirthDatePage() {
  const router = useRouter();
  const storeDate = useOnboardingStore((s) => s.birthDate);
  const storeCal = useOnboardingStore((s) => s.calendarSystem);
  const setBirthDate = useOnboardingStore((s) => s.setBirthDate);
  const setCalendarSystem = useOnboardingStore((s) => s.setCalendarSystem);

  const [value, setValue] = useState(storeDate);

  // Re-sync from the store on remount (back-navigation AC3 contract).
  useEffect(() => {
    setValue(storeDate);
  }, [storeDate]);

  const inputId = useId();
  const errorId = useId();
  const today = useMemo(() => todayIso(), []);
  const errorCode: BirthDateError | null =
    value === "" ? null : validateBirthDate(value, today);
  const errorMsg = errorCode ? birthDateErrorCopy(errorCode) : null;
  const canProceed = value !== "" && errorCode === null;

  function handleNext() {
    if (!canProceed) return;
    setBirthDate(value);
    router.push("/onboarding/birth-time");
  }

  return (
    <OnboardingChrome step={1}>
      <div className="flex flex-col gap-s2">
        <h1 className="font-display-han text-2xl text-cream-50">생년월일</h1>
        <p className="font-body text-base text-cream-300">
          먼저, 너 언제 태어났어?
        </p>
      </div>

      <div className="flex flex-col gap-s3">
        <label htmlFor={inputId} className="font-body text-sm text-cream-300">
          생년월일 (YYYY-MM-DD)
        </label>
        <input
          id={inputId}
          type="date"
          inputMode="numeric"
          autoComplete="bday"
          placeholder="1997-03-15"
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
            data-testid="birth-date-error"
          >
            {errorMsg}
          </p>
        )}
      </div>

      <div role="radiogroup" aria-label="달력 종류" className="flex gap-s2">
        <CalendarToggle
          label="양력"
          selected={storeCal === "solar"}
          onClick={() => setCalendarSystem("solar")}
        />
        <CalendarToggle
          label="음력"
          selected={storeCal === "lunar"}
          onClick={() => setCalendarSystem("lunar")}
        />
      </div>

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

interface CalendarToggleProps {
  label: "양력" | "음력";
  selected: boolean;
  onClick: () => void;
}

/**
 * Single segmented-control option — kept inline because no other onboarding
 * page reuses this radio shape. role="radio" lets axe and screen readers
 * announce the toggle correctly.
 */
function CalendarToggle({ label, selected, onClick }: CalendarToggleProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={[
        "flex-1 rounded-md border px-s4 py-s3 font-body text-base transition-colors",
        selected
          ? "border-amber-400 bg-ink-700 text-cream-50"
          : "border-cream-600 bg-ink-800 text-cream-200 hover:border-cream-300",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300",
      ].join(" ")}
    >
      {label}
    </button>
  );
}
