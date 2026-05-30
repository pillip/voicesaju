"use client";

/**
 * `/tarot/paywall` — Screen 24 (ISSUE-050).
 *
 * Quota-exhausted free users land here from `/tarot` (AC3). Renders:
 *   - Headline: "이번 주 무료 타로는 다 봤어"
 *   - Two payment option cards: 단건 결제 / 구독으로 매일 무제한
 *   - Footer caption: "다음 주 월요일에 다시 무료 1회"
 *
 * Scope: Phase-1 the option taps DON'T trigger a real payment flow —
 * the M5 billing wiring (ISSUE-088+) replaces the stubs. We render
 * the option cards as buttons with a no-op onClick so the surface is
 * already accessible and the M5 PR is purely a behaviour swap.
 *
 * Why no Suspense wrapper:
 * - We don't read `useSearchParams()` here. If a future redirect adds
 *   `?source=tarot` for analytics we'll add the Suspense boundary
 *   per the ISSUE-027 pattern.
 */

import { useRouter } from "next/navigation";

interface OptionCardProps {
  title: string;
  price: string;
  description: string;
  onTap: () => void;
}

function PaymentOptionCard({
  title,
  price,
  description,
  onTap,
}: OptionCardProps) {
  return (
    <button
      type="button"
      onClick={onTap}
      className="flex w-full flex-col gap-s2 rounded-md border border-cream-600 bg-ink-800 px-s4 py-s4 text-left text-cream-100 transition-colors hover:border-amber-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
    >
      <div className="flex items-baseline justify-between gap-s2">
        <span className="font-display-han text-lg text-cream-50">{title}</span>
        <span className="font-body text-sm font-medium text-amber-300">
          {price}
        </span>
      </div>
      <span className="font-body text-sm text-cream-300">{description}</span>
    </button>
  );
}

export default function TarotPaywallPage() {
  const router = useRouter();

  // Phase-1 stubs. Real Toss-pay flow lands in M5 — we keep the call
  // shape so the M5 PR is a 1-line swap per option.
  const onSingle = () => {
    // TODO(ISSUE-088): wire to /api/v1/billing/tarot/single
    // For now we route back to `/tarot` so the user isn't stranded.
    router.push("/tarot");
  };
  const onSubscribe = () => {
    // TODO(ISSUE-088): wire to /api/v1/billing/subscribe
    router.push("/tarot");
  };

  return (
    <main
      data-testid="tarot-paywall-screen"
      className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-s6 bg-ink-900 px-s4 py-s8 text-cream-100"
    >
      <header className="flex flex-col gap-s2 text-center">
        <h1
          className="font-display-han text-3xl text-cream-50"
          data-testid="paywall-title"
        >
          이번 주 무료 타로는 다 봤어
        </h1>
        <p
          className="font-body text-sm text-cream-300"
          data-testid="paywall-subtitle"
        >
          노인 도사가 손을 들었네.
        </p>
      </header>

      <section
        aria-label="결제 옵션"
        className="flex flex-col gap-s3"
        data-testid="paywall-options"
      >
        <PaymentOptionCard
          title="단건 결제"
          price="3,900원"
          description="이번 한 장만 바로 풀이"
          onTap={onSingle}
        />
        <PaymentOptionCard
          title="구독으로 매일 무제한"
          price="9,900원/월"
          description="매일 한 장, 사주 1회까지"
          onTap={onSubscribe}
        />
      </section>

      <footer className="mt-auto text-center">
        <p className="font-body text-xs text-cream-500">
          다음 주 월요일에 다시 무료 1회
        </p>
      </footer>
    </main>
  );
}
