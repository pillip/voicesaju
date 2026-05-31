/**
 * Frontend analytics event SDK (ISSUE-080).
 *
 * Phase-1 strategy: vendor-agnostic event emitter. Real Mixpanel /
 * PostHog SDK lands behind DEP-XX; until then ``LoggingAdapter`` is
 * the default in dev and ``NoopAdapter`` is the default in production
 * builds so we don't ship logs to end users.
 *
 * Typed event slugs are exhaustive — any new event is added to the
 * ``AnalyticsEvent`` union below, which forces every call site (and
 * test) through a type-check.
 *
 * PRD-Ref: NFR-016. Architecture-Ref: §12.1.
 */

// ---------------------------------------------------------------------------
// Event taxonomy — adding a new event requires extending the union.
// ---------------------------------------------------------------------------

export type ShareChannel = 'instagram' | 'kakao' | 'download';

export type AnalyticsEvent =
  | { name: 'onboarding_step'; properties: { step: 1 | 2 | 3 | 4 } }
  | { name: 'signup'; properties: { provider: 'kakao' | 'apple' } }
  | { name: 'paywall_view'; properties: { category: string } }
  | {
      name: 'paywall_pay';
      properties: { category: string; amount_krw: number };
    }
  | { name: 'reading_complete'; properties: { category: string } }
  | { name: 'quote_share'; properties: { channel: ShareChannel } };

export type AnalyticsEventName = AnalyticsEvent['name'];

// ---------------------------------------------------------------------------
// Adapter contract
// ---------------------------------------------------------------------------

export interface AnalyticsAdapter {
  /**
   * Emit a single event synchronously. MUST NOT throw on transport
   * errors — analytics is fire-and-forget.
   */
  track(event: AnalyticsEvent): void;
}

/** Drops every event. Default in tests + production builds. */
export class NoopAdapter implements AnalyticsAdapter {
  public readonly received: AnalyticsEvent[] = [];

  track(event: AnalyticsEvent): void {
    this.received.push(event);
  }
}

/** Console-logs every event. Default in dev. */
export class LoggingAdapter implements AnalyticsAdapter {
  track(event: AnalyticsEvent): void {
    try {
      // eslint-disable-next-line no-console
      console.info(`[analytics] ${event.name}`, event.properties);
    } catch {
      // Swallow — analytics must never crash the caller.
    }
  }
}

// ---------------------------------------------------------------------------
// Active adapter — module-level singleton
// ---------------------------------------------------------------------------

let activeAdapter: AnalyticsAdapter = new NoopAdapter();

export function getAdapter(): AnalyticsAdapter {
  return activeAdapter;
}

export function setAdapter(adapter: AnalyticsAdapter): void {
  activeAdapter = adapter;
}

export function resetAdapterForTests(): void {
  activeAdapter = new NoopAdapter();
}

// ---------------------------------------------------------------------------
// Generic emit + typed helpers
// ---------------------------------------------------------------------------

export function trackEvent(event: AnalyticsEvent): void {
  try {
    activeAdapter.track(event);
  } catch {
    // Adapter swallows internally, but guard the call boundary too.
  }
}

export function trackOnboardingStep(step: 1 | 2 | 3 | 4): void {
  trackEvent({ name: 'onboarding_step', properties: { step } });
}

export function trackSignup(provider: 'kakao' | 'apple'): void {
  trackEvent({ name: 'signup', properties: { provider } });
}

export function trackPaywallView(category: string): void {
  trackEvent({ name: 'paywall_view', properties: { category } });
}

export function trackPaywallPay(category: string, amountKrw: number): void {
  trackEvent({
    name: 'paywall_pay',
    properties: { category, amount_krw: amountKrw },
  });
}

export function trackReadingComplete(category: string): void {
  trackEvent({ name: 'reading_complete', properties: { category } });
}

export function trackQuoteShare(channel: ShareChannel): void {
  trackEvent({ name: 'quote_share', properties: { channel } });
}
