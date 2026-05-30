/**
 * Unit tests for the intro fetcher (ISSUE-032 → ISSUE-031 contract).
 *
 * The fetcher is injected with a fake `fetch` so we exercise every
 * branch (network error / non-2xx / malformed body / happy path) without
 * touching the real backend.
 */
import { describe, expect, it, vi } from "vitest";
import { fetchIntroClip, IntroFetchError } from "@/lib/api/intro";

function mkResponse(
  body: unknown,
  init: { ok?: boolean; status?: number; statusText?: string } = {},
): Response {
  const ok = init.ok ?? true;
  const status = init.status ?? (ok ? 200 : 500);
  const statusText = init.statusText ?? "";
  return {
    ok,
    status,
    statusText,
    json: async () => body,
  } as unknown as Response;
}

describe("fetchIntroClip", () => {
  it("returns the parsed payload on a 2xx response with the expected shape", async () => {
    const fakeFetch = vi.fn(async () =>
      mkResponse({
        audio_url: "tts/intro/love/known.mp3",
        subtitle: "어디 보자… 1997년생 무자년… 음, 재미있네.",
        duration_ms: 15000,
      }),
    );
    const res = await fetchIntroClip(
      "love",
      fakeFetch as unknown as typeof fetch,
    );
    expect(res.audio_url).toBe("tts/intro/love/known.mp3");
    expect(res.duration_ms).toBe(15000);
    expect(fakeFetch).toHaveBeenCalledWith(
      "/api/v1/reading/intro/love",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("URL-encodes the category segment", async () => {
    const fakeFetch = vi.fn(async () =>
      mkResponse({ audio_url: "x", subtitle: "y", duration_ms: 1 }),
    );
    await fetchIntroClip("weird/love", fakeFetch as unknown as typeof fetch);
    expect(fakeFetch).toHaveBeenCalledWith(
      "/api/v1/reading/intro/weird%2Flove",
      expect.any(Object),
    );
  });

  it("throws IntroFetchError on a non-2xx response", async () => {
    const fakeFetch = vi.fn(async () =>
      mkResponse({}, { ok: false, status: 404, statusText: "Not Found" }),
    );
    await expect(
      fetchIntroClip("love", fakeFetch as unknown as typeof fetch),
    ).rejects.toBeInstanceOf(IntroFetchError);
  });

  it("throws IntroFetchError with status=null on a network error", async () => {
    const fakeFetch = vi.fn(async () => {
      throw new Error("boom");
    });
    try {
      await fetchIntroClip("love", fakeFetch as unknown as typeof fetch);
      expect.fail("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(IntroFetchError);
      expect((err as IntroFetchError).status).toBeNull();
    }
  });

  it("throws IntroFetchError when the body shape is invalid", async () => {
    const fakeFetch = vi.fn(async () =>
      mkResponse({ audio_url: "x" /* missing subtitle/duration_ms */ }),
    );
    await expect(
      fetchIntroClip("love", fakeFetch as unknown as typeof fetch),
    ).rejects.toBeInstanceOf(IntroFetchError);
  });
});
