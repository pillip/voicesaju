/**
 * Tests for ``src/lib/sentry`` (ISSUE-078).
 *
 * Covers:
 *  1. ``initSentry`` is a no-op without a DSN.
 *  2. ``initSentry`` records init params when DSN is set.
 *  3. ``scrubEvent`` strips birth_dt / paymentKey / Toss order id / JWT.
 *  4. Sensitive dict keys are replaced regardless of value content.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { REDACTED, _resetSentryForTests, initSentry, scrubEvent } from '@/lib/sentry';

describe('initSentry', () => {
  beforeEach(() => {
    _resetSentryForTests();
  });

  it('is a no-op when DSN is undefined', () => {
    const result = initSentry({ dsn: undefined });
    expect(result).toBe(false);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((globalThis as any).__voicesaju_sentry_init__).toBeUndefined();
  });

  it('is a no-op when DSN is empty string', () => {
    const result = initSentry({ dsn: '' });
    expect(result).toBe(false);
  });

  it('records init params when DSN is set', () => {
    const result = initSentry({
      dsn: 'https://abc@example.ingest.sentry.io/1',
      environment: 'staging',
      release: 'v0.1.0',
    });

    expect(result).toBe(true);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const init = (globalThis as any).__voicesaju_sentry_init__;
    expect(init.dsn).toBe('https://abc@example.ingest.sentry.io/1');
    expect(init.environment).toBe('staging');
    expect(init.release).toBe('v0.1.0');
    expect(init.beforeSend).toBe(scrubEvent);
  });

  it('is idempotent', () => {
    const r1 = initSentry({ dsn: 'https://x@example.ingest.sentry.io/1' });
    const r2 = initSentry({ dsn: 'https://x@example.ingest.sentry.io/1' });
    expect(r1).toBe(true);
    expect(r2).toBe(true);
  });
});

describe('scrubEvent', () => {
  it('strips birth_dt from extra dict', () => {
    const cleaned = scrubEvent({
      message: 'err',
      extra: { birth_dt: '1989-04-12', category: 'love' },
    });
    expect(cleaned.extra?.birth_dt).toBe(REDACTED);
    expect(cleaned.extra?.category).toBe('love');
  });

  it('strips birth_dt from string message', () => {
    const cleaned = scrubEvent({
      message: 'signup birth_dt=1990-05-01 ok=true',
    });
    expect(cleaned.message).not.toContain('1990-05-01');
    expect(cleaned.message).toContain(REDACTED);
  });

  it('strips paymentKey from breadcrumb message', () => {
    const cleaned = scrubEvent({
      breadcrumbs: {
        values: [
          {
            message: 'POST /confirm {"paymentKey":"live_5g012345abcdefghIJKL"}',
          },
        ],
      },
    });
    const msg = (cleaned.breadcrumbs?.values?.[0] as { message?: string })?.message;
    expect(msg).toBeDefined();
    expect(msg).not.toContain('live_5g012345abcdefghIJKL');
    expect(msg).toContain(REDACTED);
  });

  it('strips Toss order id', () => {
    const cleaned = scrubEvent({
      message: 'payment.fail orderId=ORD-XQ91A4S2 amount=4900',
    });
    expect(cleaned.message).not.toContain('ORD-XQ91A4S2');
    expect(cleaned.message).toContain(REDACTED);
    expect(cleaned.message).toContain('amount=4900');
  });

  it('strips Authorization header (sensitive key)', () => {
    const cleaned = scrubEvent({
      request: {
        headers: {
          Authorization: 'Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MTIzIn0.sigabcdef',
          'X-Trace-Id': 'ok-to-keep',
        },
      },
    });
    expect(cleaned.request?.headers?.Authorization).toBe(REDACTED);
    expect(cleaned.request?.headers?.['X-Trace-Id']).toBe('ok-to-keep');
  });

  it('preserves numbers, booleans, null', () => {
    const cleaned = scrubEvent({
      message: 'ok',
      extra: { count: 5, flag: true, none: null },
    });
    expect(cleaned.extra?.count).toBe(5);
    expect(cleaned.extra?.flag).toBe(true);
    expect(cleaned.extra?.none).toBeNull();
  });
});
