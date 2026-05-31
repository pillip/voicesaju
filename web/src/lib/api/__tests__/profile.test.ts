/**
 * Unit tests for `fetchProfileMe` (ISSUE-064).
 *
 * Branch coverage:
 *   - 200 happy path returns the parsed payload.
 *   - 401 / 404 raise ProfileFetchError with the matching status.
 *   - 5xx raises ProfileFetchError with status=503.
 *   - Network failure raises ProfileFetchError with status=null.
 *   - Malformed JSON raises ProfileFetchError.
 *   - Unexpected shape raises ProfileFetchError.
 */
import { describe, expect, it, vi } from "vitest";
import {
  CORRECTION_QUOTA_EXCEEDED,
  fetchProfileMe,
  patchProfile,
  ProfileFetchError,
  type ProfileCorrectionRequest,
} from "@/lib/api/profile";

const GOOD_BODY = {
  profile_id: "p-1",
  chart_id: "c-1",
  birth_time_known: true,
  chart: {
    year: { stem: "무", branch: "자", element: "수", ten_god: "편재" },
    month: { stem: "갑", branch: "오", element: "화", ten_god: "정관" },
    day: { stem: "경", branch: "신", element: "금", ten_god: "비견" },
    hour: { stem: "정", branch: "묘", element: "목", ten_god: "정인" },
    engine_version: "saju.v1.0",
  },
};

function mkOk(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response;
}

function mkErr(status: number): Response {
  return { ok: false, status, json: async () => ({}) } as unknown as Response;
}

describe("fetchProfileMe (ISSUE-064)", () => {
  it("200 → typed payload", async () => {
    const fakeFetch = vi.fn(async () => mkOk(GOOD_BODY));
    const out = await fetchProfileMe(fakeFetch as unknown as typeof fetch);
    expect(out.profile_id).toBe("p-1");
    expect(out.chart.year.stem).toBe("무");
    expect(out.birth_time_known).toBe(true);
  });

  it("401 → ProfileFetchError with status=401", async () => {
    const fakeFetch = vi.fn(async () => mkErr(401));
    await expect(
      fetchProfileMe(fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({
      name: "ProfileFetchError",
      status: 401,
    });
  });

  it("404 → ProfileFetchError with status=404", async () => {
    const fakeFetch = vi.fn(async () => mkErr(404));
    await expect(
      fetchProfileMe(fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({
      name: "ProfileFetchError",
      status: 404,
    });
  });

  it("503 → ProfileFetchError with status=503", async () => {
    const fakeFetch = vi.fn(async () => mkErr(503));
    await expect(
      fetchProfileMe(fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({
      status: 503,
    });
  });

  it("network failure → ProfileFetchError with status=null", async () => {
    const fakeFetch = vi.fn(async () => {
      throw new Error("boom");
    });
    await expect(
      fetchProfileMe(fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({
      status: null,
    });
  });

  it("malformed JSON → ProfileFetchError", async () => {
    const fakeFetch = vi.fn(
      async () =>
        ({
          ok: true,
          status: 200,
          json: async () => {
            throw new SyntaxError("bad json");
          },
        }) as unknown as Response,
    );
    await expect(
      fetchProfileMe(fakeFetch as unknown as typeof fetch),
    ).rejects.toBeInstanceOf(ProfileFetchError);
  });

  it("unexpected body shape → ProfileFetchError", async () => {
    const fakeFetch = vi.fn(async () => mkOk({ profile_id: "x" }));
    await expect(
      fetchProfileMe(fakeFetch as unknown as typeof fetch),
    ).rejects.toBeInstanceOf(ProfileFetchError);
  });
});

// ---------------------------------------------------------------------------
// patchProfile (ISSUE-071, FR-029)
// ---------------------------------------------------------------------------

const VALID_PATCH_BODY: ProfileCorrectionRequest = {
  birth_date: "1998-09-14",
  birth_time: "09:45",
  is_lunar: false,
  gender: "F",
  name: "민지",
};

const VALID_PATCH_RESPONSE = {
  profile_id: "p-1",
  chart_id: "c-2",
  chart: GOOD_BODY.chart,
  corrections_remaining: 1,
};

function mkPatchErr(status: number, errorCode?: string): Response {
  return {
    ok: false,
    status,
    json: async () =>
      errorCode
        ? { detail: { error: { code: errorCode, message: "" } } }
        : { detail: "fail" },
  } as unknown as Response;
}

describe("patchProfile (ISSUE-071)", () => {
  it("200 → typed response with corrections_remaining", async () => {
    const fakeFetch = vi.fn(async () => mkOk(VALID_PATCH_RESPONSE));
    const out = await patchProfile(
      VALID_PATCH_BODY,
      fakeFetch as unknown as typeof fetch,
    );
    expect(out.profile_id).toBe("p-1");
    expect(out.chart_id).toBe("c-2");
    expect(out.corrections_remaining).toBe(1);
    expect(fakeFetch).toHaveBeenCalledWith(
      "/api/v1/profile",
      expect.objectContaining({
        method: "PATCH",
        credentials: "include",
      }),
    );
  });

  it("PATCH body is JSON-serialised request", async () => {
    const fakeFetch = vi.fn(async () => mkOk(VALID_PATCH_RESPONSE));
    await patchProfile(VALID_PATCH_BODY, fakeFetch as unknown as typeof fetch);
    const init = fakeFetch.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual(VALID_PATCH_BODY);
  });

  it("403 with quota code → error.message === CORRECTION_QUOTA_EXCEEDED", async () => {
    const fakeFetch = vi.fn(async () =>
      mkPatchErr(403, CORRECTION_QUOTA_EXCEEDED),
    );
    try {
      await patchProfile(
        VALID_PATCH_BODY,
        fakeFetch as unknown as typeof fetch,
      );
      throw new Error("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ProfileFetchError);
      expect((err as ProfileFetchError).status).toBe(403);
      expect((err as ProfileFetchError).message).toBe(
        CORRECTION_QUOTA_EXCEEDED,
      );
    }
  });

  it("401 → ProfileFetchError with status=401", async () => {
    const fakeFetch = vi.fn(async () => mkPatchErr(401));
    await expect(
      patchProfile(VALID_PATCH_BODY, fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({ name: "ProfileFetchError", status: 401 });
  });

  it("404 → ProfileFetchError with status=404", async () => {
    const fakeFetch = vi.fn(async () => mkPatchErr(404));
    await expect(
      patchProfile(VALID_PATCH_BODY, fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({ status: 404 });
  });

  it("network failure → ProfileFetchError with status=null", async () => {
    const fakeFetch = vi.fn(async () => {
      throw new Error("offline");
    });
    await expect(
      patchProfile(VALID_PATCH_BODY, fakeFetch as unknown as typeof fetch),
    ).rejects.toMatchObject({ status: null });
  });

  it("malformed body shape → ProfileFetchError", async () => {
    const fakeFetch = vi.fn(async () =>
      mkOk({ profile_id: "p-1", chart_id: "c-2" }),
    );
    await expect(
      patchProfile(VALID_PATCH_BODY, fakeFetch as unknown as typeof fetch),
    ).rejects.toBeInstanceOf(ProfileFetchError);
  });
});
