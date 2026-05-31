"use client";

/**
 * `/me/saju` — Screen 17 (ISSUE-064): saju chart visualization.
 *
 * Layout (top → bottom):
 *   1. TopAppBar with "사주 명식" centered title + back affordance to /me.
 *   2. `<SajuFullChart>` — 4-pillar × 4-row grid with cell tooltips +
 *      arrow-key nav + axe-clean aria-labels.
 *   3. "정보 수정하기" link → /me/edit-saju (target route lands in
 *      ISSUE-071; rendering the link unblocks the AC even though the
 *      destination is currently a 404).
 *
 * State machine:
 *   - loading: skeleton + aria-busy
 *   - error:   "잠시 후 다시 시도해주세요" + retry (5xx / network)
 *   - anonymous (401):     router.replace('/auth/login')
 *   - no profile (404):    router.replace('/onboarding')
 *   - loaded: full chart
 *
 * AC mapping (ISSUE-064):
 *   AC1 → "4 pillars render with KR character labels" (page.test.tsx +
 *         SajuFullChart.test.tsx)
 *   AC2 → "birth_time_known=false → Hour Pillar 모름, de-emphasized"
 *   AC3 → "Tap any cell → tooltip with 오행 + 십신"
 *   AC4 → "Arrow-key nav moves tooltip focus across the grid"
 *   AC5 → "Screen reader announces 년주 천간 무자, 오행 수, 십신 비견"
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { TopAppBar } from "@/components/nav/TopAppBar";
import { SajuFullChart } from "@/components/saju/SajuFullChart";
import {
  fetchProfileMe,
  ProfileFetchError,
  type ProfileMeResponse,
} from "@/lib/api/profile";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; profile: ProfileMeResponse };

export default function MeSajuPage() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  // Stable router ref so `load` can stay zero-dep without re-running on every
  // render — mirrors the pattern used by /me (ISSUE-063, see lessons
  // RL-NNN: tests mock useRouter() to return a fresh object per call, so
  // including `router` in the deps would re-fire `load` infinitely under
  // the vitest mock).
  const routerRef = useRef(router);
  routerRef.current = router;

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const profile = await fetchProfileMe();
      setState({ kind: "loaded", profile });
    } catch (err) {
      if (err instanceof ProfileFetchError && err.status === 401) {
        routerRef.current.replace("/auth/login");
        return;
      }
      if (err instanceof ProfileFetchError && err.status === 404) {
        routerRef.current.replace("/onboarding");
        return;
      }
      setState({ kind: "error", message: "잠시 후 다시 시도해주세요" });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (state.kind === "loading") {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="사주 명식" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-s4 py-s8"
          aria-busy
          data-testid="me-saju-loading"
        >
          <span className="sr-only">로딩 중</span>
        </main>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
        <TopAppBar title="사주 명식" />
        <main
          className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-s4 px-s4 py-s8"
          data-testid="me-saju-error"
        >
          <p className="font-body text-sm text-cream-300">{state.message}</p>
          <button
            type="button"
            onClick={() => {
              void load();
            }}
            className="rounded-md border border-ink-700 px-s4 py-s2 font-body text-sm text-cream-50 hover:bg-ink-800"
            data-testid="me-saju-retry"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <TopAppBar title="사주 명식" />
      <main
        className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s6 px-s4 py-s6"
        data-testid="me-saju-loaded"
      >
        <SajuFullChart
          chart={state.profile.chart}
          birthTimeKnown={state.profile.birth_time_known}
        />

        <Link
          href="/me/edit-saju"
          className="self-center rounded-md border border-ink-600 px-s4 py-s2 font-body text-sm text-cream-100 hover:bg-ink-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          data-testid="me-saju-edit-link"
        >
          정보 수정하기
        </Link>
      </main>
    </div>
  );
}
