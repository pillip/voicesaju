"use client";

/**
 * `/reading/category` — Screen 6 (ISSUE-030).
 *
 * Renders the 3-category selection screen with character greeting and an
 * entitlement status bar. This is the canonical fork point between Flow A
 * (non-member arriving from onboarding) and Flow B (logged-in user hitting
 * the 사주 tab) — both flows land here and pick a category before continuing
 * to `/reading/intro/[category]`.
 *
 * AC mapping (issues.md §ISSUE-030):
 *   AC1: 3 cards display with category-specific colors when onboarding is
 *        complete (handled by <CategoryCard> + Zustand store check).
 *   AC2: Tap card → router.push("/reading/intro/[category]").
 *   AC3: Subscriber → bottom bar "구독 중 — 이번 달 사주 X/1회 남음".
 *   AC4: Non-member → greeting uses "거기 너" (no name).
 *
 * Entitlement source:
 *   Real `GET /api/v1/me` lands in ISSUE-040. We stub via `buildMeStub` driven
 *   by a `?entitlement=<kind>` query param so dev can see every state without
 *   the real backend. The `useSearchParams` hook MUST be wrapped in <Suspense>
 *   per Next 15's App Router contract — failing to do so triggers a build-time
 *   error in the production bundle.
 */

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CategoryCard, type CategoryKey } from "@/components/ui/CategoryCard";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { buildMeStub, type MeStubResponse } from "@/lib/api/me-stub";

// Saju categories surfaced on Screen 6. Tarot lives on its own route — it is
// not part of the saju category fork.
const SAJU_CATEGORIES: ReadonlyArray<{
  key: Extract<CategoryKey, "love" | "work" | "money">;
  label: string;
  sub: string;
}> = [
  // Copy: copy_guide.md §4 (Category 1/2/3 label + sub).
  { key: "love", label: "연애", sub: "결혼? 헤어짐? 짝사랑?" },
  { key: "work", label: "직장", sub: "이직? 상사? 사업?" },
  { key: "money", label: "금전", sub: "빚? 투자? 가난할까?" },
];

interface CategoryScreenProps {
  me: MeStubResponse;
  greetingName: string | null;
}

/**
 * Resolve the greeting addressee.
 *
 * - Non-member (no name stored in the onboarding Zustand) → "거기 너" per AC4.
 * - Onboarding complete with a name → use the name verbatim.
 *
 * "Non-member" is detected via the absence of a name in the onboarding store.
 * This mirrors the Flow A scenario where the user just finished
 * `/onboarding/name` with the skip button (which clears `name` to ""). It is
 * intentionally NOT coupled to `/api/v1/me` user_id presence — that wiring
 * lands when the real `/me` endpoint replaces the stub in ISSUE-040.
 */
function resolveGreeting(name: string | null): {
  addressee: string;
  isAnonymous: boolean;
} {
  if (!name || name.trim().length === 0) {
    return { addressee: "거기 너", isAnonymous: true };
  }
  return { addressee: name.trim(), isAnonymous: false };
}

/**
 * Build the entitlement-bar copy for the given stub response.
 *
 * Source: ux_spec Screen 6 — three documented states:
 *   - "무료 토큰 1회" → free_token
 *   - "단건 결제 필요" → payment
 *   - "구독 중" / "구독 중 — 이번 달 사주 X/1회 남음" → subscription
 *
 * The non-member ("none") state falls back to "단건 결제 필요" since the
 * downstream paywall will surface the signup-grant CTA — the bottom bar here
 * is purely informational.
 */
function entitlementBarCopy(me: MeStubResponse): string {
  switch (me.entitlement_kind) {
    case "free_token":
      return "무료 토큰 1회";
    case "subscription":
      return `구독 중 — 이번 달 사주 ${me.monthly_remaining}/1회 남음`;
    case "payment":
    case "none":
    default:
      return "단건 결제 필요";
  }
}

function CategoryScreen({ me, greetingName }: CategoryScreenProps) {
  const router = useRouter();
  const { addressee } = resolveGreeting(greetingName);

  const handleSelect = (category: "love" | "work" | "money") => {
    router.push(`/reading/intro/${category}`);
  };

  // Subscriber-only sticky bottom bar with the monthly-saju remaining counter.
  // The general entitlement banner (above the cards) renders for every state;
  // the bottom bar is gated to `subscription` because ux_spec Screen 6
  // documents it as a subscriber-specific affordance.
  const isSubscriber = me.entitlement_kind === "subscription";

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-cream-100">
      <main
        className="mx-auto flex w-full max-w-md flex-1 flex-col gap-s6 px-s4 py-s8"
        data-testid="category-screen"
      >
        <header className="flex flex-col gap-s2">
          <h1
            className="font-display-han text-2xl text-cream-50"
            data-testid="greeting"
          >
            오늘은 뭐가 궁금해, {addressee}?
          </h1>
          <p
            className="font-body text-sm text-cream-300"
            data-testid="entitlement-banner"
            aria-live="polite"
          >
            {entitlementBarCopy(me)}
          </p>
        </header>

        <section
          aria-label="카테고리 선택"
          className="grid grid-cols-1 gap-s4"
          data-testid="category-grid"
        >
          {SAJU_CATEGORIES.map((cat) => (
            <CategoryCard
              key={cat.key}
              category={cat.key}
              onClick={() => handleSelect(cat.key)}
            >
              {cat.sub}
            </CategoryCard>
          ))}
        </section>
      </main>

      {isSubscriber && (
        <footer
          className="sticky bottom-0 z-20 border-t border-ink-700 bg-ink-900 px-s4 py-s3"
          data-testid="subscriber-bottom-bar"
          role="status"
        >
          <p className="font-body text-sm text-cream-100">
            구독 중 — 이번 달 사주 {me.monthly_remaining}/1회 남음
          </p>
        </footer>
      )}
    </div>
  );
}

/**
 * Suspense-bound shell. `useSearchParams` is called inside <CategoryScreen>'s
 * sibling resolver below, which is why this wrapper exists: Next 15 requires
 * any client component that reads the search params to be reachable from a
 * Suspense boundary in the SSR tree, otherwise the build emits the
 * `missing-suspense-with-csr-bailout` error.
 */
function CategoryScreenWithSearchParams() {
  const search = useSearchParams();
  const override = search.get("entitlement");
  const me = buildMeStub(override);
  // Read onboarding name from the Zustand store. The store is a module
  // singleton — outside a SSR pass it returns the in-memory state set by
  // earlier onboarding steps. On a fresh page reload the store resets, which
  // correctly yields the "non-member" anonymous greeting per AC4.
  const name = useOnboardingStore((s) => s.name);
  return <CategoryScreen me={me} greetingName={name} />;
}

export default function CategoryPage() {
  return (
    <Suspense
      fallback={
        <div
          className="flex min-h-screen items-center justify-center bg-ink-900 text-cream-100"
          aria-busy
        >
          {/* Intentionally near-empty: ux_spec Screen 6 documents load as a
              shimmer; we keep the SSR fallback minimal to avoid a flash of
              wrong content while the search-params boundary resolves. */}
          <span className="sr-only">로딩 중</span>
        </div>
      }
    >
      <CategoryScreenWithSearchParams />
    </Suspense>
  );
}
