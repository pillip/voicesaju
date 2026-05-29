"use client";

import { useCallback, useEffect, useId, useRef } from "react";
import { cn } from "@/lib/utils";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export interface ConfirmModalProps {
  /** Whether the modal is currently visible. */
  open: boolean;
  /** Called when the modal requests close (ESC, backdrop click, cancel). */
  onClose: () => void;
  /** Called when the user confirms. */
  onConfirm?: () => void;
  /** Title shown in the header (used for aria-labelledby). */
  title: React.ReactNode;
  /** Description rendered in the body. */
  description?: React.ReactNode;
  /** Confirm button label. */
  confirmLabel?: string;
  /** Cancel button label. */
  cancelLabel?: string;
  /** Optional explicit className for the panel. */
  className?: string;
  children?: React.ReactNode;
}

/**
 * Centered modal with manual focus trap and ESC-to-close.
 *
 * - `role="dialog"` + `aria-modal="true"` + `aria-labelledby={titleId}`.
 * - Tab + Shift+Tab cycle within the focusable elements inside the panel
 *   (the first focusable element receives focus on open).
 * - ESC fires `onClose`. Backdrop click also fires `onClose`.
 * - Focus is restored to the previously focused element on close.
 *
 * NO external focus-trap library — all trap logic is in this file.
 */
export function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "확인",
  cancelLabel = "취소",
  className,
  children,
}: ConfirmModalProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  const getFocusable = useCallback((): HTMLElement[] => {
    const root = panelRef.current;
    if (!root) return [];
    return Array.from(
      root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((el) => !el.hasAttribute("aria-hidden"));
  }, []);

  // Capture the previously focused element + move focus into the modal.
  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    // Defer to next tick so the panel is fully mounted before focus.
    const id = requestAnimationFrame(() => {
      const focusable = getFocusable();
      if (focusable.length > 0) {
        focusable[0].focus();
      } else {
        panelRef.current?.focus();
      }
    });
    return () => {
      cancelAnimationFrame(id);
      previouslyFocused.current?.focus?.();
    };
  }, [open, getFocusable]);

  // Key handler — ESC closes, Tab cycles focus inside.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;

      const focusable = getFocusable();
      if (focusable.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (active === first || !panelRef.current?.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last || !panelRef.current?.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose, getFocusable]);

  if (!open) return null;

  return (
    <div
      // Backdrop — clicking closes. Not focusable.
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/70 px-s4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      data-testid="confirm-modal-backdrop"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          "w-full max-w-sm rounded-md border border-ink-600 bg-ink-800 p-s6 text-cream-100 shadow-lg",
          "focus:outline-none",
          className,
        )}
      >
        <h2 id={titleId} className="font-display text-lg text-cream-50">
          {title}
        </h2>
        {description && (
          <p className="mt-s2 text-sm text-cream-200">{description}</p>
        )}
        {children}
        <div className="mt-s6 flex items-center justify-end gap-s2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-ink-600 px-s4 py-s2 text-sm text-cream-100 hover:bg-ink-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={() => {
              onConfirm?.();
              onClose();
            }}
            className="rounded-md bg-amber-400 px-s4 py-s2 text-sm font-medium text-ink-900 hover:bg-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
