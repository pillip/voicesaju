/**
 * ISSUE-095 — accessor for `NEXT_PUBLIC_QUOTE_CARD_V2`.
 *
 * Same shape as the ISSUE-094 tarot v2 flag — read-on-call so tests can
 * flip env between cases. Default is FALSE so production opts in
 * explicitly (Rollback: unset / set false → v1 layout via ISSUE-058/059).
 */
import { afterEach, describe, expect, it } from 'vitest';
import { isQuoteCardV2Enabled } from '@/lib/featureFlags';

const ENV_KEY = 'NEXT_PUBLIC_QUOTE_CARD_V2';

afterEach(() => {
  delete process.env[ENV_KEY];
});

describe('isQuoteCardV2Enabled (ISSUE-095)', () => {
  it('defaults to false when env var is unset', () => {
    delete process.env[ENV_KEY];
    expect(isQuoteCardV2Enabled()).toBe(false);
  });

  it.each(['true', 'TRUE', '1', '  true '])('returns true for env %s', (v) => {
    process.env[ENV_KEY] = v;
    expect(isQuoteCardV2Enabled()).toBe(true);
  });

  it.each(['false', '0', '', 'yes', 'on'])('returns false for env %s', (v) => {
    process.env[ENV_KEY] = v;
    expect(isQuoteCardV2Enabled()).toBe(false);
  });
});
