'use client';

import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface PrimaryButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
}

/**
 * Filled primary CTA. Amber accent on ink surface. Variants: default /
 * disabled / loading. Loading exposes aria-busy + visually-hidden announcement
 * so screen readers don't lose context (NFR-012).
 */
export const PrimaryButton = forwardRef<HTMLButtonElement, PrimaryButtonProps>(
  function PrimaryButton({ className, children, disabled, loading, type, ...rest }, ref) {
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
          'bg-amber-400 text-ink-900 transition-colors',
          'hover:bg-amber-300 active:bg-amber-500',
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
              className="inline-block h-s3 w-s3 animate-spin rounded-pill border-2 border-ink-900 border-t-transparent"
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
