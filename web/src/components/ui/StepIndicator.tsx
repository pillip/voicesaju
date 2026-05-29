'use client';

import { cn } from '@/lib/utils';

export interface StepIndicatorProps {
  total: number;
  current: number; // 1-based
  loading?: boolean;
  className?: string;
}

/**
 * N-step progress indicator (e.g. onboarding 1/3). Semantic <ol role="list">
 * with aria-current="step" on the active item; root has an aria-label
 * describing the overall progress for screen readers.
 */
export function StepIndicator({ total, current, loading, className }: StepIndicatorProps) {
  return (
    <ol
      role="list"
      aria-label={`${current} / ${total}`}
      aria-busy={loading || undefined}
      className={cn('flex w-full items-center gap-s2', className)}
    >
      {Array.from({ length: total }, (_, i) => i + 1).map((step) => {
        const isActive = step === current;
        const isDone = step < current;
        return (
          <li
            key={step}
            aria-current={isActive ? 'step' : undefined}
            className={cn(
              'h-1 flex-1 rounded-pill transition-colors',
              isActive && 'bg-amber-400',
              isDone && 'bg-cream-300',
              !isActive && !isDone && 'bg-ink-600',
            )}
          />
        );
      })}
    </ol>
  );
}
