"use client";

import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface BottomSheetProps {
  /** Whether the sheet is visible. */
  open: boolean;
  /** Called when the user dismisses (backdrop / swipe-down / ESC). */
  onClose: () => void;
  /** Accessible label for the sheet (used as aria-labelledby target). */
  title?: React.ReactNode;
  /** Distance in px the user must drag down before dismissal triggers. */
  dismissThreshold?: number;
  /** Body content. */
  children?: React.ReactNode;
  /** Override panel className. */
  className?: string;
}

/**
 * Slide-up bottom sheet with swipe-down dismissal.
 *
 * - `role="dialog"` + `aria-modal="true"` + `aria-labelledby`.
 * - ESC closes.
 * - Touch handlers track `touchstart` → `touchmove` → `touchend`; if the
 *   net vertical drag exceeds `dismissThreshold` (default 80px), the sheet
 *   fires `onClose`.
 * - NO external gesture library; touch tracking is in this file.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  dismissThreshold = 80,
  children,
  className,
}: BottomSheetProps) {
  const labelId = useId();
  const startY = useRef<number | null>(null);
  const [dragY, setDragY] = useState(0);
  const panelRef = useRef<HTMLDivElement | null>(null);

  // ESC closes.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Reset drag offset whenever visibility toggles.
  useEffect(() => {
    if (!open) setDragY(0);
  }, [open]);

  if (!open) return null;

  const handleTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    startY.current = e.touches[0]?.clientY ?? null;
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLDivElement>) => {
    if (startY.current === null) return;
    const delta = (e.touches[0]?.clientY ?? 0) - startY.current;
    if (delta > 0) {
      // Only allow downward drag.
      setDragY(delta);
    }
  };

  const handleTouchEnd = () => {
    if (dragY > dismissThreshold) {
      onClose();
    }
    startY.current = null;
    setDragY(0);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/70"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      data-testid="bottom-sheet-backdrop"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? labelId : undefined}
        tabIndex={-1}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{
          transform: dragY ? `translateY(${dragY}px)` : undefined,
          transition: dragY ? "none" : "transform 200ms ease-out",
        }}
        className={cn(
          "w-full max-w-xl rounded-t-md border-t border-ink-600 bg-ink-800 px-s4 pb-s6 pt-s2 text-cream-100 shadow-lg",
          "focus:outline-none",
          className,
        )}
        data-testid="bottom-sheet-panel"
      >
        {/* Drag handle (also a visual affordance for the swipe gesture). */}
        <div
          aria-hidden="true"
          className="mx-auto mb-s4 h-s1 w-s10 rounded-pill bg-ink-500"
        />
        {title && (
          <h2 id={labelId} className="mb-s2 font-display text-lg text-cream-50">
            {title}
          </h2>
        )}
        {children}
      </div>
    </div>
  );
}
