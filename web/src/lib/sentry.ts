/**
 * Frontend Sentry init stub (ISSUE-078).
 *
 * Architecture §12 calls for Sentry on errors. We keep the init thin
 * and DSN-gated: when ``NEXT_PUBLIC_SENTRY_DSN`` is unset, ``initSentry``
 * is a no-op so previews / local dev never ship telemetry.
 *
 * The actual ``@sentry/nextjs`` package isn't bundled at this point in
 * the project — wiring lives in this module so that when the real SDK
 * lands (with build-time sourcemap upload via ``next.config.mjs``), only
 * the body of ``initSentry`` changes; call sites stay stable.
 *
 * PRD-Ref: NFR-016.
 */

export interface SentryInitOptions {
  dsn?: string | null;
  environment?: string;
  release?: string;
  /**
   * Optional ``beforeSend`` hook that mutates the event before transport.
   * Defaults to {@link scrubEvent} which strips known PII patterns from
   * any event property (birth_dt, payment keys, Toss order IDs, JWTs).
   */
  beforeSend?: (event: SentryEventLike) => SentryEventLike | null;
}

export interface SentryEventLike {
  message?: string;
  extra?: Record<string, unknown>;
  request?: { headers?: Record<string, unknown> };
  breadcrumbs?: { values?: Array<Record<string, unknown>> };
  [key: string]: unknown;
}

export const REDACTED = '[REDACTED]';

const SENSITIVE_KEYS = new Set([
  'birth_dt',
  'birth_date',
  'birthdate',
  'birth',
  'payment_key',
  'paymentkey',
  'card_number',
  'cardnumber',
  'card_no',
  'cvv',
  'secret_key',
  'secretkey',
  'api_key',
  'apikey',
  'access_token',
  'refresh_token',
  'jwt',
  'authorization',
  'password',
  'passwd',
]);

const STRING_PATTERNS: Array<[RegExp, string]> = [
  // JWT — 3 base64url segments
  [/\beyJ[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\.[A-Za-z0-9_-]+={0,2}\b/g, REDACTED],
  // Toss order id (ORD-...)
  [/\b(?:ORD[-_])[A-Za-z0-9_-]{6,}\b/g, REDACTED],
  // paymentKey value (long alnum after `paymentKey":"` / `paymentKey=`)
  [/(paymentKey["':= ]+)[A-Za-z0-9_-]{16,}/gi, `$1${REDACTED}`],
  // birth_dt= / "birth_dt": ISO date
  [
    /(birth[_-]?(?:dt|date)\s*[=:]\s*["']?)\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?/gi,
    `$1${REDACTED}`,
  ],
];

function scrubValue(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === 'string') {
    let out = value;
    for (const [pattern, replacement] of STRING_PATTERNS) {
      out = out.replace(pattern, replacement);
    }
    return out;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (Array.isArray(value)) return value.map(scrubValue);
  if (typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = SENSITIVE_KEYS.has(k.toLowerCase()) ? REDACTED : scrubValue(v);
    }
    return out;
  }
  return value;
}

/**
 * ``before_send`` callback — recursively scrubs PII from the event tree.
 * Returns the (possibly mutated) event so transport proceeds; never
 * returns null (we always want error visibility).
 */
export function scrubEvent(event: SentryEventLike): SentryEventLike {
  return scrubValue(event) as SentryEventLike;
}

let _initialised = false;

/**
 * Initialise Sentry. Returns ``true`` iff init actually happened.
 *
 * Idempotent — calling twice is safe. When ``dsn`` is unset/empty the
 * SDK is never touched so test runs stay hermetic.
 */
export function initSentry(options: SentryInitOptions): boolean {
  const dsn = options.dsn?.trim();
  if (!dsn) return false;
  if (_initialised) return true;

  // The real ``@sentry/nextjs`` import lands here once the dependency
  // is added at deploy time. Until then we record the init parameters
  // so consumers (and tests) can verify the wiring without bundling the
  // SDK into the dev build.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).__voicesaju_sentry_init__ = {
    dsn,
    environment: options.environment ?? 'local',
    release: options.release ?? null,
    beforeSend: options.beforeSend ?? scrubEvent,
  };
  _initialised = true;
  return true;
}

/**
 * Test-only reset. Avoid using in production code.
 */
export function _resetSentryForTests(): void {
  _initialised = false;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (globalThis as any).__voicesaju_sentry_init__;
}
