/**
 * Typed fetcher for `GET /api/v1/reading/intro/{category}` (ISSUE-031).
 *
 * Consumed by the `/reading/intro/[category]` player (ISSUE-032). The shape
 * mirrors the backend Pydantic model `IntroClipResponse` in
 * `api/voicesaju/readings/routers/intro.py`:
 *
 *   { audio_url: str, subtitle: str, duration_ms: int }
 *
 * Phase 1 behavior (documented in the backend router):
 *  - `audio_url` is a raw R2 path like `tts/intro/love/known.mp3` until
 *    ISSUE-038 wires the R2 signing service. The player must tolerate the
 *    underlying audio asset returning 404 by surfacing the "탭해서 듣기"
 *    fallback (ISSUE-032 AC3).
 *  - `subtitle` is the cached Korean intro script from copy_guide §5 / §3
 *    (LLM-generated subtitles land with ISSUE-039).
 *
 * Errors from the backend:
 *  - 401 → caller is anonymous (no auth cookie). We surface this as a
 *    generic `IntroFetchError` and the caller renders the static-subtitle
 *    fallback — same UX as a network failure.
 *  - 404 → no profile yet OR no clip seeded for the variant. Same fallback.
 *  - 5xx / network errors → same fallback.
 *
 * The page-level component (`page.tsx`) decides whether to show fallback
 * or rethrow; this module deliberately does NOT throw a typed-error
 * hierarchy because the UX collapses all failure modes onto a single
 * "탭해서 듣기 + static subtitle" branch.
 */

export interface IntroClipResponse {
  audio_url: string;
  subtitle: string;
  duration_ms: number;
}

export class IntroFetchError extends Error {
  readonly status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "IntroFetchError";
    this.status = status;
  }
}

/**
 * Fetch the intro clip metadata for `category`.
 *
 * Throws `IntroFetchError` on any non-2xx response or network failure.
 * The route handler in `page.tsx` catches this and switches to the
 * fallback branch.
 *
 * @param category one of "love" | "work" | "money" — the backend
 *   returns 404 for any unseeded category, which the page treats as
 *   "no intro available, render fallback".
 * @param fetchImpl injectable for tests. Production passes `fetch`.
 */
export async function fetchIntroClip(
  category: string,
  fetchImpl: typeof fetch = fetch,
): Promise<IntroClipResponse> {
  let res: Response;
  try {
    res = await fetchImpl(
      `/api/v1/reading/intro/${encodeURIComponent(category)}`,
      {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      },
    );
  } catch (err) {
    throw new IntroFetchError(
      `network error fetching intro for ${category}: ${
        err instanceof Error ? err.message : String(err)
      }`,
      null,
    );
  }

  if (!res.ok) {
    throw new IntroFetchError(
      `intro fetch failed: ${res.status} ${res.statusText}`,
      res.status,
    );
  }

  const json = (await res.json()) as unknown;
  if (
    !json ||
    typeof json !== "object" ||
    typeof (json as Record<string, unknown>).audio_url !== "string" ||
    typeof (json as Record<string, unknown>).subtitle !== "string" ||
    typeof (json as Record<string, unknown>).duration_ms !== "number"
  ) {
    throw new IntroFetchError("intro response shape invalid", res.status);
  }
  return json as IntroClipResponse;
}
