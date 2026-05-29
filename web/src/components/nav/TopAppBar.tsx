'use client';

import { cn } from '@/lib/utils';

export interface TopAppBarProps extends Omit<React.HTMLAttributes<HTMLElement>, 'title'> {
  /** Optional back affordance (typically a button/anchor). */
  back?: React.ReactNode;
  /** Centered title content. */
  title?: React.ReactNode;
  /** Optional right-aligned action (e.g. settings icon). */
  action?: React.ReactNode;
}

/**
 * Top-of-screen chrome with three slots: back / title / action.
 *
 * - Renders as a `<header>`. When placed at the top level of a page the
 *   browser/axe implicitly assigns `role="banner"`. We intentionally do NOT
 *   set the role explicitly so the component can also be embedded inside
 *   other landmarks (e.g. demo pages, sectioning containers) without
 *   tripping axe's `landmark-banner-is-top-level` rule.
 * - The title slot is announced via the `<h1>` for screen-reader users.
 */
export function TopAppBar({ back, title, action, className, ...rest }: TopAppBarProps) {
  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-[56px] items-center justify-between gap-s2 border-b border-ink-700 bg-ink-900 px-s4',
        className,
      )}
      {...rest}
    >
      <div className="flex min-w-[44px] items-center justify-start">{back}</div>
      <div className="flex flex-1 items-center justify-center">
        {typeof title === 'string' ? (
          <h1 className="truncate font-display text-base text-cream-50">{title}</h1>
        ) : (
          title
        )}
      </div>
      <div className="flex min-w-[44px] items-center justify-end">{action}</div>
    </header>
  );
}
