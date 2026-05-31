/**
 * Unit tests for the history API fetchers (ISSUE-066).
 *
 * Mirrors the patterns established in `profile.test.ts` and `me.test.ts`.
 */
import { describe, expect, it, vi } from 'vitest';

import {
  fetchMyReadings,
  HistoryFetchError,
  probeReadingAudio,
  readingAudioUrl,
} from '@/lib/api/history';

const VALID_ROW = {
  id: 'r-1',
  category: 'love',
  started_at: '2026-05-29T07:30:00+00:00',
  completed_at: '2026-05-29T07:31:30+00:00',
  audio_available: true,
  summary: '별기운이 좋네…',
};

function mkOkResponse(body: unknown, status = 200): Response {
  return {
    ok: true,
    status,
    json: async () => body,
  } as unknown as Response;
}

function mkErrResponse(status: number): Response {
  return {
    ok: false,
    status,
    json: async () => ({ error: 'fail' }),
  } as unknown as Response;
}

describe('readingAudioUrl', () => {
  it('builds the canonical audio URL for a reading id', () => {
    expect(readingAudioUrl('abc-123')).toBe('/api/v1/reading/abc-123/audio.mp3');
  });

  it('URL-encodes the reading id', () => {
    expect(readingAudioUrl('a/b c')).toBe('/api/v1/reading/a%2Fb%20c/audio.mp3');
  });
});

describe('fetchMyReadings', () => {
  it('returns the parsed list on 200', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkOkResponse([VALID_ROW]));
    const rows = await fetchMyReadings(1, fetchImpl);
    expect(rows).toEqual([VALID_ROW]);
    expect(fetchImpl).toHaveBeenCalledWith(
      '/api/v1/me/readings?page=1',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      }),
    );
  });

  it('propagates 401 as HistoryFetchError with status=401', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkErrResponse(401));
    await expect(fetchMyReadings(1, fetchImpl)).rejects.toMatchObject({
      name: 'HistoryFetchError',
      status: 401,
    });
  });

  it('propagates 500 as HistoryFetchError with status=500', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkErrResponse(500));
    await expect(fetchMyReadings(1, fetchImpl)).rejects.toMatchObject({
      name: 'HistoryFetchError',
      status: 500,
    });
  });

  it('wraps network errors with status=null', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error('boom'));
    try {
      await fetchMyReadings(1, fetchImpl);
      throw new Error('should have thrown');
    } catch (err) {
      expect(err).toBeInstanceOf(HistoryFetchError);
      expect((err as HistoryFetchError).status).toBeNull();
    }
  });

  it('rejects malformed shapes', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkOkResponse({ not: 'an array' }));
    await expect(fetchMyReadings(1, fetchImpl)).rejects.toBeInstanceOf(HistoryFetchError);
  });

  it('rejects rows missing required fields', async () => {
    const bad = { ...VALID_ROW, audio_available: 'yes' };
    const fetchImpl = vi.fn().mockResolvedValue(mkOkResponse([bad]));
    await expect(fetchMyReadings(1, fetchImpl)).rejects.toBeInstanceOf(HistoryFetchError);
  });

  it('paginates via the page param', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkOkResponse([]));
    await fetchMyReadings(3, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith('/api/v1/me/readings?page=3', expect.anything());
  });
});

describe('probeReadingAudio', () => {
  it('returns available=true on 200', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
    } as unknown as Response);
    const result = await probeReadingAudio('r-1', fetchImpl);
    expect(result).toEqual({ available: true });
  });

  it('returns available=true on 206 (partial content)', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      status: 206,
      ok: true,
    } as unknown as Response);
    expect(await probeReadingAudio('r-1', fetchImpl)).toEqual({
      available: true,
    });
  });

  it('returns available=false + expired=true on 410', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      status: 410,
      ok: false,
    } as unknown as Response);
    const result = await probeReadingAudio('r-1', fetchImpl);
    expect(result).toEqual({ available: false, expired: true });
  });

  it('throws HistoryFetchError on 401', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      status: 401,
      ok: false,
    } as unknown as Response);
    await expect(probeReadingAudio('r-1', fetchImpl)).rejects.toMatchObject({
      name: 'HistoryFetchError',
      status: 401,
    });
  });

  it('throws HistoryFetchError on 404', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      status: 404,
      ok: false,
    } as unknown as Response);
    await expect(probeReadingAudio('r-1', fetchImpl)).rejects.toMatchObject({
      name: 'HistoryFetchError',
      status: 404,
    });
  });

  it('wraps network errors', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error('offline'));
    await expect(probeReadingAudio('r-1', fetchImpl)).rejects.toBeInstanceOf(HistoryFetchError);
  });
});
