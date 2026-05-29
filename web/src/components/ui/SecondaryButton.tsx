'use client';

import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface SecondaryButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
}

/**
 * Outline secondary CTA. Used alongside PrimaryButton for cancel/secondary
 * actions. Same a11y contract as PrimaryButton.
 */
export const SecondaryButton = forwardRef<HTMLButtonElement, SecondaryButtonProps>(
  function SecondaryButton({ className, children, disabled, loading, type, ...rest }, ref) {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type ?? 'button'}
        disabled={isDisabled}
        aria-disabled={isDisabled || undefined}
        aria-busy={loading || undefined}
        className={cn(
          'inline-flex items-center justify-center gap-s2 rounded-md px-s4 py-s2 font-body text-base font-medium',
          'border border-cream-300 bg-transparent text-cream-100 transition-colors',
          'hover:bg-ink-700 active:bg-ink-600',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...rest}
      >
        {loading ? (
          <>
            <span
              aria-hidden="true"
              className="inline-block h-s3 w-s3 animate-spin rounded-pill border-2 border-cream-100 border-t-transparent"
            />
            <span className="sr-only">로딩 중</span>
            {children}
          </>
        ) : (
          children
        )}
      </button>
    );
  },
);
