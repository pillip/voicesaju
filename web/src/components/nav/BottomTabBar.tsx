"use client";

import type { AnchorHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type TabKey = "saju" | "tarot" | "me";

export interface BottomTab {
  /** Stable id for the tab. */
  key: TabKey;
  /** Visible label (Korean per UX spec). */
  label: string;
  /** Destination href. */
  href: string;
  /** Optional inline icon (svg/emoji). */
  icon?: React.ReactNode;
}

export interface BottomTabBarProps extends Omit<
  React.HTMLAttributes<HTMLElement>,
  "role"
> {
  /** Which tab is currently active. */
  active?: TabKey;
  /** Hide the bar (e.g. during audio playback per FR-024). */
  hideOnPlayback?: boolean;
  /** Override the default 3 tabs (사주 / 오늘의 타로 / 마이). */
  tabs?: BottomTab[];
}

const DEFAULT_TABS: BottomTab[] = [
  { key: "saju", label: "사주", href: "/" },
  { key: "tarot", label: "오늘의 타로", href: "/tarot" },
  { key: "me", label: "마이", href: "/me" },
];

/**
 * Fixed bottom navigation chrome. Renders a `<nav role="navigation">` with
 * three primary tabs. When `hideOnPlayback` is true the component returns
 * `null` so that the DOM is empty during long-running audio sessions
 * (FR-024 — minimize chrome distractions during reading playback).
 *
 * Accessibility:
 * - `aria-label="주요 메뉴"`.
 * - The active tab carries `aria-current="page"` and a visible underline.
 * - Tap targets meet the 44×44 minimum recommended by WCAG 2.5.5.
 */
export function BottomTabBar({
  active,
  hideOnPlayback = false,
  tabs = DEFAULT_TABS,
  className,
  ...rest
}: BottomTabBarProps) {
  if (hideOnPlayback) {
    return null;
  }
  return (
    <nav
      role="navigation"
      aria-label="주요 메뉴"
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 flex h-[64px] items-stretch border-t border-ink-700 bg-ink-900",
        className,
      )}
      {...rest}
    >
      <ul className="flex flex-1 list-none items-stretch">
        {tabs.map((tab) => {
          const isActive = tab.key === active;
          const props: AnchorHTMLAttributes<HTMLAnchorElement> = {
            href: tab.href,
          };
          if (isActive) {
            props["aria-current"] = "page";
          }
          return (
            <li key={tab.key} className="flex flex-1">
              <a
                {...props}
                data-tab-key={tab.key}
                className={cn(
                  "flex min-h-[44px] flex-1 flex-col items-center justify-center gap-s1 px-s2 py-s2",
                  "text-xs font-medium transition-colors",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-amber-300",
                  isActive
                    ? "text-amber-300 underline decoration-amber-300 underline-offset-4"
                    : "text-cream-300 hover:text-cream-100",
                )}
              >
                {tab.icon && (
                  <span aria-hidden="true" className="text-lg">
                    {tab.icon}
                  </span>
                )}
                <span>{tab.label}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
