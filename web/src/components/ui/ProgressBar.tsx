"use client";

import { cn } from "@/lib/utils";

export interface ProgressBarProps {
  /** Current value in the same unit as `max`. Clamped to [0, max]. */
  value: number;
  /** Maximum value. Defaults to 100 (percentage semantics). */
  max?: number;
  /** Optional className for the outer track. */
  className?: string;
  /** Accessible label announced by screen readers. */
  label: string;
  /** Optional testid for the outer track. */
  "data-testid"?: string;
}

/**
 * Thin progress indicator used by the intro player (ISSUE-032).
 *
 * Intentionally minimal — a flexbox div with a width transition is enough
 * per the issue scope ("Don't gold-plate the progress bar"). The component
 * exposes a proper ARIA progressbar role for accessibility.
 *
 * The width is computed as a percentage of `max`, clamped to [0, 100] so a
 * runaway audio timestamp can never overflow the track.
 */
export function ProgressBar({
  value,
  max = 100,
  className,
  label,
  "data-testid": testId,
}: ProgressBarProps) {
  const safeMax = max > 0 ? max : 1;
  const clamped = Math.max(0, Math.min(value, safeMax));
  const percent = (clamped / safeMax) * 100;

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={safeMax}
      aria-valuenow={clamped}
      data-testid={testId}
      className={cn(
        "h-[3px] w-full overflow-hidden rounded-pill bg-ink-700",
        className,
      )}
    >
      <div
        className="h-full bg-amber-400 transition-[width] duration-150 ease-linear"
        style={{ width: `${percent}%` }}
        data-testid={testId ? `${testId}-fill` : undefined}
      />
    </div>
  );
}
