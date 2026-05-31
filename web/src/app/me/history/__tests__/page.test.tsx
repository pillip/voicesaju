/**
 * Unit tests for `/me/history/[id]` (ISSUE-066, Screen 19).
 *
 * AC mapping (issues.md §ISSUE-066):
 *   AC1: past reading → `<audio>` element rendered with the audio URL.
 *   AC2: audio expired → "이 풀이는 더 이상 재생할 수 없습니다" copy.
 *   AC3: tap pause → audio stops (native behaviour; we assert the
 *        `<audio controls>` element is in the tree so the browser
 *        provides the pause affordance).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const replaceMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: replaceMock,
    back: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

import { MeHistoryItemView as MeHistoryItemPage } from '@/app/me/history/[id]/MeHistoryItemView';

function mkResponse(status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => ({}),
  } as unknown as Response;
}

describe('MeHistoryItemPage', () => {
  beforeEach(() => {
    replaceMock.mockReset();
  });

  it('AC1: renders the <audio controls> element when the blob is available', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkResponse(200));

    render(<MeHistoryItemPage params={{ id: 'r-1' }} fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId('me-history-loaded')).toBeInTheDocument();
    });

    const audio = screen.getByTestId('me-history-audio') as HTMLAudioElement;
    expect(audio).toBeInTheDocument();
    expect(audio.tagName).toBe('AUDIO');
    // AC3: native controls present so the browser renders pause/play
    // — testing-library doesn't render shadow DOM, so we assert the
    // attribute rather than the rendered button.
    expect(audio).toHaveAttribute('controls');
    // Source points at the archive endpoint (FR-028, AC1).
    expect(audio).toHaveAttribute('src', '/api/v1/reading/r-1/audio.mp3');
  });

  it('AC2: shows the expired-audio fallback when probe returns 410', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkResponse(410));

    render(<MeHistoryItemPage params={{ id: 'r-1' }} fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId('me-history-expired')).toBeInTheDocument();
    });
    expect(screen.getByText('이 풀이는 더 이상 재생할 수 없습니다')).toBeInTheDocument();
    // Back-to-me link affordance per ux_spec.
    expect(screen.getByTestId('me-history-back-link')).toHaveAttribute('href', '/me');
  });

  it("AC: 401 → router.replace('/auth/login')", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkResponse(401));

    render(<MeHistoryItemPage params={{ id: 'r-1' }} fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/auth/login');
    });
  });

  it("AC: 404 → router.replace('/me')", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkResponse(404));

    render(<MeHistoryItemPage params={{ id: 'r-1' }} fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/me');
    });
  });

  it("network error → 'error' state with retry that re-triggers fetch", async () => {
    const fetchImpl = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(mkResponse(200));

    render(<MeHistoryItemPage params={{ id: 'r-1' }} fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId('me-history-error')).toBeInTheDocument();
    });
    expect(screen.getByText('잠시 후 다시 시도해주세요')).toBeInTheDocument();

    // Tap retry → should re-run the probe → loaded.
    fireEvent.click(screen.getByTestId('me-history-retry'));

    await waitFor(() => {
      expect(screen.getByTestId('me-history-loaded')).toBeInTheDocument();
    });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it('renders the archive ribbon', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(mkResponse(200));

    render(<MeHistoryItemPage params={{ id: 'r-1' }} fetchImpl={fetchImpl} />);

    await waitFor(() => {
      expect(screen.getByTestId('me-history-ribbon')).toBeInTheDocument();
    });
    // Default ribbon copy when no ?d= query param is present.
    expect(screen.getByTestId('me-history-ribbon').textContent).toContain('[풀이]');
  });
});
