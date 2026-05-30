/**
 * Unit tests for `/reading/play` (ISSUE-042 — Screen 9).
 *
 * AC1: SSE connects → loading state then audio starts.
 * AC2: pause UI surfaced via VoicePlayer (covered by ISSUE-033 unit tests).
 * AC3: SajuChart tooltip (covered by `<SajuChart>` unit tests).
 * AC4: offline event → "네트워크 연결이 끊겼습니다" banner.
 * AC5: online event → reconnect (SSE source factory called twice).
 * AC6: pipeline error event → "별기운이 잠시 약하네…" full-screen + buttons.
 *
 * We mock `next/navigation`, `<VoicePlayer>` (its full MSE stack is
 * already covered in ISSUE-033 tests), and the SSE source factory.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import type { ChunkEvent } from '@/lib/audio/events';
import type { PipelineErrorEvent, ReadingSSESource } from '@/lib/audio/sse-source';

const pushMock = vi.fn();
const replaceMock = vi.fn();
let searchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock, back: vi.fn() }),
  useSearchParams: () => searchParams,
}));

// Stub VoicePlayer so the heavy MSE wiring stays out of the page test.
vi.mock('@/components/audio', () => {
  return {
    VoicePlayer: ({ ariaLabel, onEnded }: { ariaLabel?: string; onEnded?: () => void }) => (
      <section data-testid="voice-player-stub" aria-label={ariaLabel ?? '음성 플레이어'}>
        <button type="button" onClick={onEnded} data-testid="stub-end-trigger">
          stub end
        </button>
      </section>
    ),
    FR_034_BANNER_TEXT: '음성 서비스가 일시적으로 불가합니다.',
  };
});

import PlayClient from '@/app/reading/play/PlayClient';

interface StubSource extends ReadingSSESource {
  triggerPipelineError: (reason: PipelineErrorEvent['reason']) => void;
  triggerConnectionError: () => void;
}

function makeStubSource(): StubSource {
  const lastOffsetMs = 0;
  let closed = false;
  let onPipe: ((e: PipelineErrorEvent) => void) | null = null;
  let onConn: (() => void) | null = null;
  const source: StubSource = {
    [Symbol.asyncIterator]: () => ({
      next: async (): Promise<IteratorResult<ChunkEvent>> => ({
        value: undefined as unknown as ChunkEvent,
        done: true,
      }),
    }),
    get lastOffsetMs() {
      return lastOffsetMs;
    },
    get connected() {
      return !closed;
    },
    close() {
      closed = true;
    },
    triggerPipelineError(reason) {
      onPipe?.({ type: 'pipeline_error', reason });
    },
    triggerConnectionError() {
      onConn?.();
    },
  };
  // Late-binding the handlers via the factory below.
  (source as unknown as { _bind: (a: unknown, b: unknown) => void })._bind = (a, b) => {
    onPipe = a as (e: PipelineErrorEvent) => void;
    onConn = b as () => void;
  };
  return source;
}

describe('/reading/play — Screen 9 (ISSUE-042)', () => {
  beforeEach(() => {
    pushMock.mockReset();
    replaceMock.mockReset();
    searchParams = new URLSearchParams({ reading_id: 'abc-123' });
  });

  it('AC1: with ?reading_id set, opens the SSE source and renders the player layout', async () => {
    const stub = makeStubSource();
    const factory = vi.fn((readingId: string, options) => {
      (stub as unknown as { _bind: (a: unknown, b: unknown) => void })._bind(
        options.onPipelineError,
        options.onConnectionError,
      );
      return stub;
    });
    await act(async () => {
      render(<PlayClient sseSourceFactory={factory} disableNetworkListeners />);
    });
    expect(factory).toHaveBeenCalledWith('abc-123', expect.anything());
    expect(screen.getByTestId('play-shell')).toBeInTheDocument();
    expect(screen.getByTestId('voice-player-stub')).toBeInTheDocument();
    expect(screen.getByTestId('saju-chart')).toBeInTheDocument();
  });

  it('AC4: offline event surfaces the network-drop banner with 네트워크 연결이 끊겼습니다', async () => {
    const stub = makeStubSource();
    const factory = vi.fn((_id: string, options) => {
      (stub as unknown as { _bind: (a: unknown, b: unknown) => void })._bind(
        options.onPipelineError,
        options.onConnectionError,
      );
      return stub;
    });
    await act(async () => {
      render(<PlayClient sseSourceFactory={factory} />);
    });
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(screen.getByTestId('network-banner').textContent).toBe('네트워크 연결이 끊겼습니다');
    expect(screen.getByTestId('play-shell').getAttribute('data-runtime-state')).toBe(
      'network_drop',
    );
  });

  it('AC5: online event after offline re-opens the SSE source (reconnect)', async () => {
    const stub = makeStubSource();
    const factory = vi.fn((_id: string, options) => {
      (stub as unknown as { _bind: (a: unknown, b: unknown) => void })._bind(
        options.onPipelineError,
        options.onConnectionError,
      );
      return stub;
    });
    await act(async () => {
      render(<PlayClient sseSourceFactory={factory} />);
    });
    expect(factory).toHaveBeenCalledTimes(1);
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(screen.getByTestId('play-shell').getAttribute('data-runtime-state')).toBe(
      'network_drop',
    );
    act(() => {
      window.dispatchEvent(new Event('online'));
    });
    // The factory is called once on mount + once after reconnect.
    expect(factory).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('play-shell').getAttribute('data-runtime-state')).toBe('streaming');
  });

  it('AC6: a pipeline_error from the SSE adapter renders the full-screen 별기운 takeover with both CTAs', async () => {
    const stub = makeStubSource();
    const factory = vi.fn((_id: string, options) => {
      (stub as unknown as { _bind: (a: unknown, b: unknown) => void })._bind(
        options.onPipelineError,
        options.onConnectionError,
      );
      return stub;
    });
    await act(async () => {
      render(<PlayClient sseSourceFactory={factory} disableNetworkListeners />);
    });
    act(() => {
      stub.triggerPipelineError('llm_failure');
    });
    const errEl = screen.getByTestId('play-error');
    expect(errEl.textContent).toMatch(/별기운이 잠시 약하네/);
    // Both CTAs render.
    expect(screen.getByTestId('retry-button')).toBeInTheDocument();
    expect(screen.getByTestId('navigate-my-button')).toBeInTheDocument();
    // 마이페이지로 tap routes to /me.
    fireEvent.click(screen.getByTestId('navigate-my-button'));
    expect(pushMock).toHaveBeenCalledWith('/me');
  });

  it('redirects to /reading/category when neither reading_id nor category is provided', async () => {
    searchParams = new URLSearchParams();
    await act(async () => {
      render(<PlayClient disableNetworkListeners />);
    });
    expect(replaceMock).toHaveBeenCalledWith('/reading/category');
  });

  it('renders the ended-CTA after the VoicePlayer reports onEnded', async () => {
    const stub = makeStubSource();
    const factory = vi.fn((_id: string, options) => {
      (stub as unknown as { _bind: (a: unknown, b: unknown) => void })._bind(
        options.onPipelineError,
        options.onConnectionError,
      );
      return stub;
    });
    await act(async () => {
      render(<PlayClient sseSourceFactory={factory} disableNetworkListeners />);
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('stub-end-trigger'));
    });
    expect(screen.getByTestId('ended-cta')).toBeInTheDocument();
  });

  it('calls createReading when only ?category is provided', async () => {
    searchParams = new URLSearchParams({ category: 'love' });
    const stub = makeStubSource();
    const createReadingImpl = vi.fn(async () => ({
      reading_id: 'freshly-minted',
      sse_url: '/api/v1/reading/freshly-minted/stream',
      audio_stream_url: '/api/v1/reading/freshly-minted/audio',
    }));
    const factory = vi.fn((_id: string, options) => {
      (stub as unknown as { _bind: (a: unknown, b: unknown) => void })._bind(
        options.onPipelineError,
        options.onConnectionError,
      );
      return stub;
    });
    await act(async () => {
      render(
        <PlayClient
          createReadingImpl={createReadingImpl}
          sseSourceFactory={factory}
          disableNetworkListeners
        />,
      );
    });
    expect(createReadingImpl).toHaveBeenCalledWith({ category: 'love' });
    // Once the create resolves the factory should have been called with
    // the returned reading_id.
    expect(factory).toHaveBeenCalledWith('freshly-minted', expect.anything());
  });
});
