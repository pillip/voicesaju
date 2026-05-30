/**
 * Typed fetcher for `GET /api/v1/me` (ISSUE-040 contract, consumed by ISSUE-063).
 *
 * Backend pydantic shape (api/voicesaju/users/routers/me.py):
 *
 * ```
 * {
 *   "user_id": "uuid-or-null",
 *   "entitlement": {
 *     "kind": "free_token" | "subscription" | "none",
 *     "token_id": "...",
 *     "subscription_id": "...",
 *     "has_anything": bool,
 *     "requires_payment": bool
 *   }
 * }
 * ```
 *
 * Phase 1 caveat: the backend route is "safe to call without a session" — it
 * synthesizes `user_id=null, entitlement.kind="none"` for anonymous callers
 * and returns 200. The `/me` page (Screen 16) treats this 200-but-anonymous
 * payload as "redirect to /auth/login" because Screen 16 is a member-only
 * hub. We deliberately key the auth check on `user_id` rather than the HTTP
 * status so the page survives the future migration to a 401-on-anonymous
 * endpoint without rewriting the caller.
 *
 * Errors:
 *   - Network failure or non-2xx → `MeFetchError` (caller renders retry UI).
 *   - JSON parse failure → also `MeFetchError`.
 *   - `user_id == null` in a 2xx body is NOT an error here — the page maps it
 *     to a `router.replace('/auth/login')` per AC3.
 */

export type EntitlementKind = 'free_token' | 'subscription' | 'none';

export interface MeEntitlement {
  kind: EntitlementKind;
  token_id: string | null;
  subscription_id: string | null;
  has_anything: boolean;
  requires_payment: boolean;
}

export interface MeResponse {
  user_id: string | null;
  entitlement: MeEntitlement;
}

export class MeFetchError extends Error {
  readonly status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = 'MeFetchError';
    this.status = status;
  }
}

/**
 * Fetch the caller's `/me` payload.
 *
 * @param fetchImpl injectable for tests. Production passes the global `fetch`.
 */
export async function fetchMe(fetchImpl: typeof fetch = fetch): Promise<MeResponse> {
  let res: Response;
  try {
    res = await fetchImpl('/api/v1/me', {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
  } catch (err) {
    throw new MeFetchError(
      `network error fetching /me: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }

  if (!res.ok) {
    throw new MeFetchError(`non-OK response from /me: HTTP ${res.status}`, res.status);
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch (err) {
    throw new MeFetchError(
      `malformed JSON from /me: ${err instanceof Error ? err.message : String(err)}`,
      res.status,
    );
  }

  if (!isMeResponse(body)) {
    throw new MeFetchError(`unexpected shape from /me`, res.status);
  }

  return body;
}

function isMeResponse(value: unknown): value is MeResponse {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  if (!('user_id' in v) || !('entitlement' in v)) return false;
  if (v.user_id !== null && typeof v.user_id !== 'string') return false;
  const ent = v.entitlement;
  if (typeof ent !== 'object' || ent === null) return false;
  const e = ent as Record<string, unknown>;
  if (e.kind !== 'free_token' && e.kind !== 'subscription' && e.kind !== 'none') return false;
  if (typeof e.has_anything !== 'boolean') return false;
  if (typeof e.requires_payment !== 'boolean') return false;
  return true;
}
