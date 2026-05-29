'use client';

import type { PropsWithChildren } from 'react';
import { cn } from '@/lib/utils';

export type ToastTone = 'info' | 'success' | 'warning' | 'error';

export interface ToastProps {
  tone?: ToastTone;
  loading?: boolean;
  className?: string;
}

const TONE_BG: Record<ToastTone, string> = {
  info: 'bg-state-info text-cream-50',
  success: 'bg-state-success text-cream-50',
  warning: 'bg-state-warning text-ink-900',
  error: 'bg-state-error text-cream-50',
};

/**
 * Transient toast notification. Tone determines both the background and the
 * announcement role:
 *   - `error` → role="alert" (assertive — interrupts SR users)
 *   - others → role="status" + aria-live="polite"
 */
export function Toast({
  tone = 'info',
  loading,
  className,
  children,
}: PropsWithChildren<ToastProps>) {
  const isAlert = tone === 'error';
  return (
    <div
      role={isAlert ? 'alert' : 'status'}
      aria-live={isAlert ? undefined : 'polite'}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center gap-s2 rounded-md px-s4 py-s2 font-body text-sm shadow-md',
        TONE_BG[tone],
        className,
      )}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="inline-block h-s3 w-s3 animate-spin rounded-pill border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </div>
  );
}
