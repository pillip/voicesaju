"use client";

import { useState } from "react";
import { BottomTabBar, TopAppBar } from "@/components/nav";
import { BottomSheet, ConfirmModal } from "@/components/ui";

/**
 * Client island that demos the four ISSUE-022 nav/modal primitives on
 * the /preview page. The base preview page stays server-rendered for
 * speed; only this island is hydrated.
 */
export function NavChromePreview() {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <section
      aria-labelledby="section-nav-chrome"
      className="flex flex-col gap-s4 border-b border-ink-600 py-s6"
    >
      <header className="flex flex-col gap-s2">
        <h2
          id="section-nav-chrome"
          className="font-display text-2xl text-cream-50"
        >
          Nav chrome (ISSUE-022)
        </h2>
        <p className="text-sm text-cream-300">
          BottomTabBar / TopAppBar / ConfirmModal / BottomSheet.
        </p>
      </header>

      {/* Static demos */}
      <div className="relative overflow-hidden rounded-md border border-ink-600 bg-ink-800 p-s4">
        <TopAppBar
          back={
            <button
              type="button"
              className="rounded-md px-s2 py-s1 text-sm text-cream-100"
            >
              뒤로
            </button>
          }
          title="설정"
          action={
            <button
              type="button"
              className="rounded-md px-s2 py-s1 text-sm text-cream-100"
            >
              완료
            </button>
          }
        />
        <div className="h-s10" />
        <BottomTabBar
          active="saju"
          className="relative inset-x-auto bottom-auto"
        />
      </div>

      {/* Interactive triggers */}
      <div className="flex flex-wrap gap-s2">
        <button
          type="button"
          onClick={() => setConfirmOpen(true)}
          className="rounded-md bg-amber-400 px-s4 py-s2 text-sm font-medium text-ink-900"
          data-testid="preview-open-confirm"
        >
          ConfirmModal 열기
        </button>
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          className="rounded-md bg-amber-400 px-s4 py-s2 text-sm font-medium text-ink-900"
          data-testid="preview-open-sheet"
        >
          BottomSheet 열기
        </button>
      </div>

      <ConfirmModal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => setConfirmOpen(false)}
        title="삭제 확인"
        description="정말로 계정을 삭제할까요?"
      />
      <BottomSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        title="공유하기"
      >
        <p className="text-sm text-cream-200">
          아래에서 공유 방식을 선택하세요.
        </p>
      </BottomSheet>
    </section>
  );
}
