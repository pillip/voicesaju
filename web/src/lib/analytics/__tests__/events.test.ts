/**
 * Unit tests for the frontend analytics event SDK (ISSUE-080).
 *
 * AC coverage:
 * - AC1 (onboarding): trackOnboardingStep emits ``onboarding_step`` with
 *   the right step number for each of the four onboarding screens.
 * - AC2 (quote share): trackQuoteShare emits ``quote_share`` with one of
 *   ``instagram | kakao | download``.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  LoggingAdapter,
  NoopAdapter,
  getAdapter,
  resetAdapterForTests,
  setAdapter,
  trackEvent,
  trackOnboardingStep,
  trackPaywallPay,
  trackPaywallView,
  trackQuoteShare,
  trackReadingComplete,
  trackSignup,
} from '../events';

beforeEach(() => {
  resetAdapterForTests();
});

describe('analytics adapter wiring', () => {
  it('defaults to a NoopAdapter after reset', () => {
    expect(getAdapter()).toBeInstanceOf(NoopAdapter);
  });

  it('lets a caller swap the active adapter', () => {
    const custom = new NoopAdapter();
    setAdapter(custom);
    expect(getAdapter()).toBe(custom);
  });

  it('NoopAdapter records events for assertion-friendliness', () => {
    const noop = new NoopAdapter();
    setAdapter(noop);
    trackEvent({ name: 'onboarding_step', properties: { step: 1 } });
    expect(noop.received).toHaveLength(1);
    expect(noop.received[0].name).toBe('onboarding_step');
  });
});

describe('trackOnboardingStep — AC1', () => {
  it('emits onboarding_step for each of the four onboarding screens', () => {
    const noop = new NoopAdapter();
    setAdapter(noop);
    trackOnboardingStep(1);
    trackOnboardingStep(2);
    trackOnboardingStep(3);
    trackOnboardingStep(4);
    expect(noop.received.map((e) => e.name)).toEqual([
      'onboarding_step',
      'onboarding_step',
      'onboarding_step',
      'onboarding_step',
    ]);
    expect(
      noop.received.map((e) => (e.name === 'onboarding_step' ? e.properties.step : null)),
    ).toEqual([1, 2, 3, 4]);
  });
});

describe('trackQuoteShare — AC2', () => {
  it.each(['instagram', 'kakao', 'download'] as const)(
    'emits quote_share with channel=%s',
    (channel) => {
      const noop = new NoopAdapter();
      setAdapter(noop);
      trackQuoteShare(channel);
      expect(noop.received).toHaveLength(1);
      const ev = noop.received[0];
      expect(ev.name).toBe('quote_share');
      if (ev.name === 'quote_share') {
        expect(ev.properties.channel).toBe(channel);
      }
    },
  );
});

describe('typed helpers carry their expected payloads', () => {
  it('signup carries provider', () => {
    const noop = new NoopAdapter();
    setAdapter(noop);
    trackSignup('kakao');
    expect(noop.received[0]).toEqual({
      name: 'signup',
      properties: { provider: 'kakao' },
    });
  });

  it('paywall_view carries category', () => {
    const noop = new NoopAdapter();
    setAdapter(noop);
    trackPaywallView('career');
    expect(noop.received[0]).toEqual({
      name: 'paywall_view',
      properties: { category: 'career' },
    });
  });

  it('paywall_pay carries amount + category', () => {
    const noop = new NoopAdapter();
    setAdapter(noop);
    trackPaywallPay('love', 4900);
    expect(noop.received[0]).toEqual({
      name: 'paywall_pay',
      properties: { category: 'love', amount_krw: 4900 },
    });
  });

  it('reading_complete carries category', () => {
    const noop = new NoopAdapter();
    setAdapter(noop);
    trackReadingComplete('career');
    expect(noop.received[0]).toEqual({
      name: 'reading_complete',
      properties: { category: 'career' },
    });
  });
});

describe('LoggingAdapter never throws', () => {
  it('swallows errors from the underlying transport', () => {
    const adapter = new LoggingAdapter();
    // Replace console.info with one that throws to simulate transport
    // failure. The adapter MUST NOT propagate.
    const original = console.info;
    console.info = () => {
      throw new Error('boom');
    };
    try {
      expect(() =>
        adapter.track({
          name: 'onboarding_step',
          properties: { step: 1 },
        }),
      ).not.toThrow();
    } finally {
      console.info = original;
    }
  });
});

describe('trackEvent does not crash when the adapter throws', () => {
  it('swallows adapter errors at the call site', () => {
    const broken: { track: (event: never) => void } = {
      track: () => {
        throw new Error('vendor down');
      },
    };
    setAdapter(broken as unknown as NoopAdapter);
    expect(() => trackEvent({ name: 'onboarding_step', properties: { step: 2 } })).not.toThrow();
  });
});
