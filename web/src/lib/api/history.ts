/**
 * Typed fetchers for the history routes (ISSUE-066 backend).
 *
 *   GET /api/v1/me/readings           — paginated list
 *   GET /api/v1/reading/{id}/audio.mp3 — archived audio replay
 *
 * The audio endpoint is consumed directly by the `<audio>` element via
 * its `src` prop, so we only need to expose a URL builder + an
 * existence/availability check for the JSON shape.
 *
 * Backend pydantic shape (`api/voicesaju/readings/routers/history.py`
 * `ReadingHistoryRow`):
 *
 * ```
 * {
 *   "id": "uuid",
 *   "category": "love" | "work" | "money" | "tarot",
 *   "started_at": "2026-05-29T07:30:00+00:00" | null,
 *   "completed_at": "2026-05-29T07:31:30+00:00" | null,
 *   "audio_available": bool,
 *   "summary": "별기운이 좋네…" | null
 * }
 * ```
 *
 * Status mapping (consumed by `/me/history` and `/me/history/[id]`):
 *  - 200 → `ReadingHistoryRow[]` / audio blob.
 *  - 401 → `HistoryFetchError` with `status=401` (page → redirect /auth/login).
 *  - 404 → `HistoryFetchError` with `status=404` (page → 404 surface).
 *  - 410 → `HistoryFetchError` with `status=410` (page → "audio expired" copy).
 *  - 5xx / network / parse → generic error (page → "잠시 후 다시 시도해주세요").
 */

export interface ReadingHistoryRow {
  id: string;
  category: string;
  started_at: string | null;
  completed_at: string | null;
  audio_available: boolean;
  summary: string | null;
}

export class HistoryFetchError extends Error {
  readonly status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = 'HistoryFetchError';
    this.status = status;
  }
}

/**
 * Build the archived-audio URL for a given reading. The frontend
 * passes this string into the `<audio>` element's `src` so the
 * browser handles streaming + pause/seek natively.
 */
export function readingAudioUrl(readingId: string): string {
  return `/api/v1/reading/${encodeURIComponent(readingId)}/audio.mp3`;
}

/**
 * Fetch the caller's reading history (paginated).
 *
 * @param page  1-indexed page number. Defaults to 1.
 * @param fetchImpl  injectable for tests. Production passes the global `fetch`.
 */
export async function fetchMyReadings(
  page: number = 1,
  fetchImpl: typeof fetch = fetch,
): Promise<ReadingHistoryRow[]> {
  let res: Response;
  try {
    res = await fetchImpl(`/api/v1/me/readings?page=${page}`, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
  } catch (err) {
    throw new HistoryFetchError(
      `network error fetching /me/readings: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }

  if (!res.ok) {
    throw new HistoryFetchError(
      `non-OK response from /me/readings: HTTP ${res.status}`,
      res.status,
    );
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch (err) {
    throw new HistoryFetchError(
      `malformed JSON from /me/readings: ${err instanceof Error ? err.message : String(err)}`,
      res.status,
    );
  }

  if (!Array.isArray(body) || !body.every(isReadingHistoryRow)) {
    throw new HistoryFetchError(`unexpected shape from /me/readings`, res.status);
  }

  return body;
}

/**
 * HEAD-style probe of the audio URL to decide which UI variant to show.
 *
 * The archived-audio endpoint returns 200 for "blob present" and 410
 * for "expired" — calling this once on mount lets the page render the
 * expired-audio fallback (AC2) without first attempting a failed
 * `<audio>` element load (which spams the console with
 * MEDIA_ERR_SRC_NOT_SUPPORTED).
 *
 * @returns `{ available: true }` for HTTP 200,
 *          `{ available: false, expired: true }` for HTTP 410,
 *          and throws `HistoryFetchError` for any other status.
 */
export async function probeReadingAudio(
  readingId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ available: true } | { available: false; expired: boolean }> {
  let res: Response;
  try {
    // We use GET (not HEAD) because some HTTP clients/middlewares
    // strip HEAD bodies and the mock storage layer's KeyError fallback
    // wouldn't fire. The browser caches the GET so the subsequent
    // `<audio>` element call doesn't re-fetch.
    res = await fetchImpl(readingAudioUrl(readingId), {
      method: 'GET',
      credentials: 'include',
      // Range:bytes=0-0 keeps the response body tiny when the server
      // honours it; when it doesn't, the cost is the full file (~1MB)
      // — acceptable for Phase-1 where files are mock-sized.
      headers: { Range: 'bytes=0-0' },
    });
  } catch (err) {
    throw new HistoryFetchError(
      `network error probing audio: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }

  // 200 OK or 206 Partial Content both mean "blob present".
  if (res.status === 200 || res.status === 206) {
    return { available: true };
  }
  if (res.status === 410) {
    return { available: false, expired: true };
  }
  throw new HistoryFetchError(`non-OK response from audio: HTTP ${res.status}`, res.status);
}

function isReadingHistoryRow(value: unknown): value is ReadingHistoryRow {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  if (typeof v.id !== 'string') return false;
  if (typeof v.category !== 'string') return false;
  if (v.started_at !== null && typeof v.started_at !== 'string') return false;
  if (v.completed_at !== null && typeof v.completed_at !== 'string') return false;
  if (typeof v.audio_available !== 'boolean') return false;
  if (v.summary !== null && typeof v.summary !== 'string') return false;
  return true;
}
