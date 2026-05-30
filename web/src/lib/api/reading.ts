/**
 * Reading-pipeline API client (ISSUE-042).
 *
 * Thin typed wrapper around the ISSUE-039 backend:
 *   POST /api/v1/reading           — create a Reading row + return SSE URL.
 *   GET  /api/v1/reading/{id}/stream — SSE chunk stream (consumed via
 *                                     `lib/audio/sse-source.ts`, not here).
 *
 * The page-level shell on `/reading/play` calls `createReading()` only
 * when no `reading_id` query param is provided — i.e. when the user
 * landed via the paywall flow (Flow A) and we need to spin up a fresh
 * pipeline. When a `reading_id` is already in the URL the page skips
 * the create call and goes straight to SSE.
 */

export interface CreateReadingRequest {
  category: 'love' | 'work' | 'money';
  character_key?: 'nuna' | 'dosa';
}

export interface CreateReadingResponse {
  reading_id: string;
  sse_url: string;
  audio_stream_url: string;
}

export class ReadingApiError extends Error {
  readonly status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = 'ReadingApiError';
    this.status = status;
  }
}

export async function createReading(
  body: CreateReadingRequest,
  fetchImpl: typeof fetch = fetch,
): Promise<CreateReadingResponse> {
  let res: Response;
  try {
    res = await fetchImpl(`/api/v1/reading`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new ReadingApiError(
      `network error creating reading: ${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }
  if (!res.ok) {
    throw new ReadingApiError(`createReading failed with status ${res.status}`, res.status);
  }
  const json = (await res.json()) as CreateReadingResponse;
  return json;
}
