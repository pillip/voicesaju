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
