/**
 * Unit tests for the `/api/v1/me` fetcher (ISSUE-063 supporting module).
 *
 * Exercises every branch of `fetchMe` without touching the real backend:
 *   - happy path: 2xx + valid shape → returns parsed body
 *   - anonymous: 2xx with `user_id: null` is a successful payload (NOT an error)
 *   - network failure: rejected promise → MeFetchError(status=null)
 *   - non-2xx: 401/500 → MeFetchError(status=status)
 *   - malformed JSON: throw at .json() → MeFetchError
 *   - unexpected shape: missing `entitlement` → MeFetchError
 */
import { describe, expect, it, vi } from 'vitest';
import { fetchMe, MeFetchError } from '@/lib/api/me';

function mkResponse(body: unknown, init: { ok?: boolean; status?: number } = {}): Response {
  const ok = init.ok ?? true;
  const status = init.status ?? (ok ? 200 : 500);
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

describe('fetchMe', () => {
  it('returns the parsed payload for a member (subscription kind)', async () => {
    const fakeFetch = vi.fn(async () =>
      mkResponse({
        user_id: 'u-1',
        entitlement: {
          kind: 'subscription',
          token_id: null,
          subscription_id: 'sub-1',
          has_anything: true,
          requires_payment: false,
        },
      }),
    );
    const res = await fetchMe(fakeFetch as unknown as typeof fetch);
    expect(res.user_id).toBe('u-1');
    expect(res.entitlement.kind).toBe('subscription');
    expect(res.entitlement.subscription_id).toBe('sub-1');
    expect(fakeFetch).toHaveBeenCalledWith(
      '/api/v1/me',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('returns the anonymous shape (user_id=null) as a successful payload', async () => {
    const fakeFetch = vi.fn(async () =>
      mkResponse({
        user_id: null,
        entitlement: {
          kind: 'none',
          token_id: null,
          subscription_id: null,
          has_anything: false,
          requires_payment: true,
        },
      }),
    );
    const res = await fetchMe(fakeFetch as unknown as typeof fetch);
    expect(res.user_id).toBeNull();
    expect(res.entitlement.kind).toBe('none');
  });

  it('throws MeFetchError(status=null) on a rejected fetch (network error)', async () => {
    const fakeFetch = vi.fn(async () => {
      throw new Error('boom');
    });
    await expect(fetchMe(fakeFetch as unknown as typeof fetch)).rejects.toBeInstanceOf(
      MeFetchError,
    );
    try {
      await fetchMe(fakeFetch as unknown as typeof fetch);
    } catch (err) {
      const e = err as MeFetchError;
      expect(e.status).toBeNull();
    }
  });

  it('throws MeFetchError with the HTTP status on a non-2xx response', async () => {
    const fakeFetch = vi.fn(async () => mkResponse({}, { ok: false, status: 503 }));
    try {
      await fetchMe(fakeFetch as unknown as typeof fetch);
      throw new Error('expected MeFetchError to be thrown');
    } catch (err) {
      expect(err).toBeInstanceOf(MeFetchError);
      expect((err as MeFetchError).status).toBe(503);
    }
  });

  it('throws MeFetchError when .json() fails', async () => {
    const fakeFetch = vi.fn(
      async () =>
        ({
          ok: true,
          status: 200,
          json: async () => {
            throw new Error('not json');
          },
        }) as unknown as Response,
    );
    await expect(fetchMe(fakeFetch as unknown as typeof fetch)).rejects.toBeInstanceOf(
      MeFetchError,
    );
  });

  it('throws MeFetchError on an unexpected payload shape', async () => {
    const fakeFetch = vi.fn(async () => mkResponse({ user_id: 'u-1' /* no entitlement */ }));
    await expect(fetchMe(fakeFetch as unknown as typeof fetch)).rejects.toBeInstanceOf(
      MeFetchError,
    );
  });

  it('rejects an entitlement.kind outside the allowed enum', async () => {
    const fakeFetch = vi.fn(async () =>
      mkResponse({
        user_id: 'u-1',
        entitlement: {
          kind: 'mystery_kind',
          token_id: null,
          subscription_id: null,
          has_anything: false,
          requires_payment: true,
        },
      }),
    );
    await expect(fetchMe(fakeFetch as unknown as typeof fetch)).rejects.toBeInstanceOf(
      MeFetchError,
    );
  });
});
