'use client';

import { forwardRef } from 'react';
import type { AnchorHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface TertiaryLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  disabled?: boolean;
}

/**
 * Underline-on-hover tertiary link. Renders as <a> so it remains usable with
 * external URLs as well as Next.js client routing (consumers can wrap with
 * <Link> if needed). Disabled variant blocks keyboard focus.
 */
export const TertiaryLink = forwardRef<HTMLAnchorElement, TertiaryLinkProps>(function TertiaryLink(
  { className, children, disabled, href, tabIndex, ...rest },
  ref,
) {
  return (
    <a
      ref={ref}
      href={href}
      aria-disabled={disabled || undefined}
      tabIndex={disabled ? -1 : tabIndex}
      onClick={disabled ? (e) => e.preventDefault() : rest.onClick}
      className={cn(
        'inline-flex items-center font-body text-sm text-cream-200 underline decoration-cream-400 underline-offset-4 transition-colors',
        'hover:text-amber-300 hover:decoration-amber-300',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
        disabled && 'pointer-events-none opacity-50',
        className,
      )}
      {...rest}
    >
      {children}
    </a>
  );
});
