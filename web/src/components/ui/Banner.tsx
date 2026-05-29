'use client';

import type { PropsWithChildren } from 'react';
import { cn } from '@/lib/utils';

export type BannerTone = 'info' | 'success' | 'warning' | 'error';

export interface BannerProps {
  tone?: BannerTone;
  disabled?: boolean;
  className?: string;
}

const TONE_CLASSES: Record<BannerTone, string> = {
  info: 'border-state-info bg-ink-800 text-cream-100',
  success: 'border-state-success bg-ink-800 text-cream-100',
  warning: 'border-state-warning bg-ink-800 text-cream-50',
  error: 'border-state-error bg-ink-800 text-cream-50',
};

/**
 * Persistent banner (page-top or inline). High-tone (warning/error) is
 * announced as `role="alert"`; info/success is `role="status"`.
 */
export function Banner({
  tone = 'info',
  disabled,
  className,
  children,
}: PropsWithChildren<BannerProps>) {
  const isAlert = tone === 'warning' || tone === 'error';
  return (
    <div
      role={isAlert ? 'alert' : 'status'}
      aria-live={isAlert ? undefined : 'polite'}
      aria-disabled={disabled || undefined}
      className={cn(
        'w-full rounded-md border-l-4 px-s4 py-s3 font-body text-sm',
        TONE_CLASSES[tone],
        disabled && 'opacity-50',
        className,
      )}
    >
      {children}
    </div>
  );
}
