/**
 * Typed fetcher for `GET /api/v1/profile/me` (ISSUE-064 backend addition).
 *
 * Backend pydantic shape (api/voicesaju/users/routers/profile.py
 * `ProfileMeResponse`):
 *
 * ```
 * {
 *   "profile_id": "uuid",
 *   "chart_id": "uuid",
 *   "chart": {
 *     "year":  { "stem", "branch", "element", "ten_god" },
 *     "month": { "stem", "branch", "element", "ten_god" },
 *     "day":   { "stem", "branch", "element", "ten_god" },
 *     "hour":  { "stem", "branch", "element", "ten_god" } | null,
 *     "engine_version": "saju.v1..."
 *   },
 *   "birth_time_known": bool
 * }
 * ```
 *
 * Status mapping (consumed by `/me/saju` page):
 *  - 200 → `ProfileMeResponse`.
 *  - 401 → `ProfileFetchError` with `status=401` (page → redirect /auth/login).
 *  - 404 → `ProfileFetchError` with `status=404` (page → redirect /onboarding).
 *  - 5xx / network / parse → `ProfileFetchError` with arbitrary status
 *    (page → "잠시 후 다시 시도해주세요" + retry).
 */

export type SajuElement = "목" | "화" | "토" | "금" | "수";

export interface SajuPillar {
  stem: string;
  branch: string;
  element: SajuElement | string;
  ten_god: string | null;
}

export interface SajuChartPayload {
  year: SajuPillar;
  month: SajuPillar;
  day: SajuPillar;
  hour: SajuPillar | null;
  engine_version: string;
}

export interface ProfileMeResponse {
  profile_id: string;
  chart_id: string;
  chart: SajuChartPayload;
  birth_time_known: boolean;
}

export class ProfileFetchError extends Error {
  readonly status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ProfileFetchError";
    this.status = status;
  }
}

/**
 * Fetch the caller's persisted profile + saju chart.
 *
 * @param fetchImpl injectable for tests. Production passes the global `fetch`.
 */
export async function fetchProfileMe(
  fetchImpl: typeof fetch = fetch,
): Promise<ProfileMeResponse> {
  let res: Response;
  try {
    res = await fetchImpl("/api/v1/profile/me", {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    throw new ProfileFetchError(
      `network error fetching /profile/me: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }

  if (!res.ok) {
    throw new ProfileFetchError(
      `non-OK response from /profile/me: HTTP ${res.status}`,
      res.status,
    );
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch (err) {
    throw new ProfileFetchError(
      `malformed JSON from /profile/me: ${err instanceof Error ? err.message : String(err)}`,
      res.status,
    );
  }

  if (!isProfileMeResponse(body)) {
    throw new ProfileFetchError(
      `unexpected shape from /profile/me`,
      res.status,
    );
  }

  return body;
}

function isProfileMeResponse(value: unknown): value is ProfileMeResponse {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  if (typeof v.profile_id !== "string") return false;
  if (typeof v.chart_id !== "string") return false;
  if (typeof v.birth_time_known !== "boolean") return false;
  const c = v.chart;
  if (typeof c !== "object" || c === null) return false;
  const chart = c as Record<string, unknown>;
  if (!isPillar(chart.year) || !isPillar(chart.month) || !isPillar(chart.day))
    return false;
  if (chart.hour !== null && !isPillar(chart.hour)) return false;
  if (typeof chart.engine_version !== "string") return false;
  return true;
}

function isPillar(value: unknown): value is SajuPillar {
  if (typeof value !== "object" || value === null) return false;
  const p = value as Record<string, unknown>;
  if (typeof p.stem !== "string") return false;
  if (typeof p.branch !== "string") return false;
  if (typeof p.element !== "string") return false;
  if (p.ten_god !== null && typeof p.ten_god !== "string") return false;
  return true;
}

// ---------------------------------------------------------------------------
// PATCH /api/v1/profile (ISSUE-071, FR-029)
// ---------------------------------------------------------------------------

export interface ProfileCorrectionRequest {
  birth_date: string;
  birth_time: string | null;
  is_lunar: boolean;
  gender: "M" | "F";
  name?: string | null;
}

export interface ProfileCorrectionResponse {
  profile_id: string;
  chart_id: string;
  chart: SajuChartPayload;
  corrections_remaining: number;
}

/**
 * Error code returned by the backend when the caller has burned
 * through both free corrections. Surfaced verbatim so the page can
 * branch into the 운영 문의 fallback (AC3) without reading the message.
 */
export const CORRECTION_QUOTA_EXCEEDED = "correction_quota_exceeded";

/**
 * PATCH the caller's saju profile.
 *
 * Status mapping:
 *  - 200 → `ProfileCorrectionResponse` (counter incremented).
 *  - 401 → `ProfileFetchError` with `status=401` (page → /auth/login).
 *  - 403 → `ProfileFetchError` with `status=403` (page → 운영 문의 fallback).
 *    The thrown error's message starts with the upstream `error.code`
 *    so callers can branch on `correction_quota_exceeded` without
 *    parsing the body twice.
 *  - 404 → `ProfileFetchError` with `status=404` (page → /onboarding).
 *  - 5xx/network/parse → generic `ProfileFetchError`.
 *
 * @param fetchImpl injectable for tests. Production passes the global `fetch`.
 */
export async function patchProfile(
  body: ProfileCorrectionRequest,
  fetchImpl: typeof fetch = fetch,
): Promise<ProfileCorrectionResponse> {
  let res: Response;
  try {
    res = await fetchImpl("/api/v1/profile", {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new ProfileFetchError(
      `network error patching /profile: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }

  if (!res.ok) {
    // Try to extract the upstream `error.code` so the page can
    // distinguish quota-exhausted from generic 403s.
    let errorCode: string | null = null;
    try {
      const errBody = (await res.json()) as {
        detail?: { error?: { code?: string } };
      };
      errorCode = errBody?.detail?.error?.code ?? null;
    } catch {
      // Ignore — fall through with the status-only error.
    }
    throw new ProfileFetchError(
      errorCode ?? `non-OK response from /profile PATCH: HTTP ${res.status}`,
      res.status,
    );
  }

  let respBody: unknown;
  try {
    respBody = await res.json();
  } catch (err) {
    throw new ProfileFetchError(
      `malformed JSON from /profile PATCH: ${err instanceof Error ? err.message : String(err)}`,
      res.status,
    );
  }

  if (!isProfileCorrectionResponse(respBody)) {
    throw new ProfileFetchError(
      `unexpected shape from /profile PATCH`,
      res.status,
    );
  }

  return respBody;
}

function isProfileCorrectionResponse(
  value: unknown,
): value is ProfileCorrectionResponse {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  if (typeof v.profile_id !== "string") return false;
  if (typeof v.chart_id !== "string") return false;
  if (typeof v.corrections_remaining !== "number") return false;
  const c = v.chart;
  if (typeof c !== "object" || c === null) return false;
  const chart = c as Record<string, unknown>;
  if (!isPillar(chart.year) || !isPillar(chart.month) || !isPillar(chart.day))
    return false;
  if (chart.hour !== null && !isPillar(chart.hour)) return false;
  if (typeof chart.engine_version !== "string") return false;
  return true;
}
