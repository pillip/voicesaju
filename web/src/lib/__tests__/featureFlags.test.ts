/**
 * Unit tests for the v2 feature-flag accessor (ISSUE-094).
 *
 * The flag is read from `process.env.NEXT_PUBLIC_TAROT_V2_SPREAD`. The
 * accessor lives in `lib/featureFlags` so future v2 flags (e.g.
 * `QUOTE_CARD_V2` for ISSUE-095) get a single place to land without
 * sprinkling `process.env.NEXT_PUBLIC_*` lookups across components.
 *
 * Default behaviour: when the env var is unset the flag is FALSE so
 * production rolls v2 out via explicit opt-in. The Rollback section of
 * the issue keys off the same flag — flipping it to `false` reverts
 * `/tarot` to the legacy single-card layout from ISSUE-051.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { isNavV2Enabled, isTarotV2SpreadEnabled } from '@/lib/featureFlags';

const ENV_KEY = 'NEXT_PUBLIC_TAROT_V2_SPREAD';
const NAV_ENV_KEY = 'NEXT_PUBLIC_NAV_V2';

afterEach(() => {
  delete process.env[ENV_KEY];
  delete process.env[NAV_ENV_KEY];
});

describe('isTarotV2SpreadEnabled (ISSUE-094)', () => {
  it('defaults to false when env var is unset', () => {
    delete process.env[ENV_KEY];
    expect(isTarotV2SpreadEnabled()).toBe(false);
  });

  it('returns true for env "true"', () => {
    process.env[ENV_KEY] = 'true';
    expect(isTarotV2SpreadEnabled()).toBe(true);
  });

  it('returns true for env "1"', () => {
    process.env[ENV_KEY] = '1';
    expect(isTarotV2SpreadEnabled()).toBe(true);
  });

  it('returns false for env "false"', () => {
    process.env[ENV_KEY] = 'false';
    expect(isTarotV2SpreadEnabled()).toBe(false);
  });

  it('returns false for unrelated env values', () => {
    process.env[ENV_KEY] = 'maybe';
    expect(isTarotV2SpreadEnabled()).toBe(false);
  });
});

describe('isNavV2Enabled (ISSUE-096)', () => {
  it('defaults to false when env var is unset', () => {
    delete process.env[NAV_ENV_KEY];
    expect(isNavV2Enabled()).toBe(false);
  });

  it('returns true for env "true" / "1" / "TRUE"', () => {
    process.env[NAV_ENV_KEY] = 'true';
    expect(isNavV2Enabled()).toBe(true);
    process.env[NAV_ENV_KEY] = '1';
    expect(isNavV2Enabled()).toBe(true);
    process.env[NAV_ENV_KEY] = 'TRUE';
    expect(isNavV2Enabled()).toBe(true);
  });

  it('returns false for env "false" or unrelated', () => {
    process.env[NAV_ENV_KEY] = 'false';
    expect(isNavV2Enabled()).toBe(false);
    process.env[NAV_ENV_KEY] = 'maybe';
    expect(isNavV2Enabled()).toBe(false);
    process.env[NAV_ENV_KEY] = '';
    expect(isNavV2Enabled()).toBe(false);
  });

  it('is independent of the tarot flag', () => {
    process.env[ENV_KEY] = 'true';
    delete process.env[NAV_ENV_KEY];
    expect(isNavV2Enabled()).toBe(false);
    expect(isTarotV2SpreadEnabled()).toBe(true);
  });
});
