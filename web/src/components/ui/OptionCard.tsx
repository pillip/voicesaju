'use client';

import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface OptionCardProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
  loading?: boolean;
}

/**
 * Radio-like selection card (e.g. gender, time-known options during the
 * onboarding flow). role="radio" so screen readers describe it accurately.
 */
export const OptionCard = forwardRef<HTMLButtonElement, OptionCardProps>(function OptionCard(
  { className, children, selected, disabled, loading, ...rest },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <button
      ref={ref}
      type="button"
      role="radio"
      aria-checked={selected ?? false}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      disabled={isDisabled}
      className={cn(
        'flex w-full items-center justify-between gap-s2 rounded-md border px-s4 py-s3 font-body text-left text-base transition-colors',
        selected
          ? 'border-amber-400 bg-ink-700 text-cream-50'
          : 'border-cream-600 bg-ink-800 text-cream-200 hover:border-cream-300',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
        isDisabled && 'cursor-not-allowed opacity-50',
        className,
      )}
      {...rest}
    >
      <span>{children}</span>
      {loading && <span className="sr-only">로딩 중</span>}
    </button>
  );
});
