/**
 * Unit tests for the SSE → ChunkEventSource adapter (ISSUE-042).
 *
 * We inject a `FakeEventSource` to avoid hitting the browser
 * EventSource API, which jsdom does not implement. Tests cover the
 * three named event types the backend pipeline (ISSUE-039) emits and
 * the disconnect/error paths the page shell reacts to.
 */
import { describe, expect, it, vi } from 'vitest';
import { openReadingSSESource } from '@/lib/audio/sse-source';
import type { ChunkEvent } from '@/lib/audio/events';

interface FakeMessageEvent {
  data: string;
}

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  readonly opts: EventSourceInit | undefined;
  listeners = new Map<string, Array<(e: FakeMessageEvent) => void>>();
  closed = false;
  constructor(url: string, opts?: EventSourceInit) {
    this.url = url;
    this.opts = opts;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: (e: FakeMessageEvent) => void) {
    const list = this.listeners.get(name) ?? [];
    list.push(fn);
    this.listeners.set(name, list);
  }
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  removeEventListener(_name: string, _fn: unknown) {
    /* no-op for tests */
  }
  close() {
    this.closed = true;
  }
  dispatch(name: string, data?: unknown) {
    const list = this.listeners.get(name) ?? [];
    // Native EventSource error events have no `.data` property — our
    // adapter detects this via `typeof e.data === "string"`. Model it
    // by stripping `data` entirely when the caller passes `undefined`.
    const event = (data === undefined ? {} : { data: data as string }) as FakeMessageEvent;
    for (const fn of list) fn(event);
  }
}

async function drain(source: AsyncIterable<ChunkEvent>): Promise<ChunkEvent[]> {
  const out: ChunkEvent[] = [];
  for await (const ev of source) {
    out.push(ev);
  }
  return out;
}

describe('openReadingSSESource (ISSUE-042)', () => {
  it('forwards subtitle / audio_ready / end events to the iterator in order', async () => {
    FakeEventSource.instances = [];
    const source = openReadingSSESource('reading-1', {
      EventSourceCtor: FakeEventSource as unknown as typeof EventSource,
    });
    const es = FakeEventSource.instances[0];

    es.dispatch('open');
    es.dispatch('subtitle', JSON.stringify({ text: '별기운이 있다', audio_offset_ms: 0 }));
    es.dispatch('audio_ready', JSON.stringify({ seq: 0, url: 'https://r2/chunks/0.mp3' }));
    es.dispatch('subtitle', JSON.stringify({ text: '그대에게', audio_offset_ms: 200 }));
    es.dispatch('audio_ready', JSON.stringify({ seq: 1, url: 'https://r2/chunks/1.mp3' }));
    es.dispatch('end', JSON.stringify({ reading_id: 'reading-1', duration_ms: 400 }));

    const events = await drain(source);
    expect(events).toHaveLength(5);
    expect(events[0]).toMatchObject({ type: 'subtitle', text: '별기운이 있다' });
    expect(events[1]).toMatchObject({
      type: 'audio_ready',
      seq: 0,
      url: 'https://r2/chunks/0.mp3',
    });
    expect(events[3]).toMatchObject({ type: 'audio_ready', seq: 1 });
    expect(events[4]).toMatchObject({ type: 'end' });
    expect(source.lastOffsetMs).toBe(200);
    expect(es.closed).toBe(true);
  });

  it('fires onPipelineError when the backend emits `event: error` with JSON data', async () => {
    FakeEventSource.instances = [];
    const onPipelineError = vi.fn();
    const source = openReadingSSESource('reading-2', {
      EventSourceCtor: FakeEventSource as unknown as typeof EventSource,
      onPipelineError,
    });
    const es = FakeEventSource.instances[0];

    es.dispatch('error', JSON.stringify({ reason: 'llm_failure', message: 'Claude returned 500' }));

    // Iterator should terminate after the error.
    const events = await drain(source);
    expect(events).toEqual([]);
    expect(onPipelineError).toHaveBeenCalledWith({
      type: 'pipeline_error',
      reason: 'llm_failure',
      message: 'Claude returned 500',
    });
    expect(es.closed).toBe(true);
  });

  it('fires onConnectionError on a native EventSource error (no data)', async () => {
    FakeEventSource.instances = [];
    const onConnectionError = vi.fn();
    const source = openReadingSSESource('reading-3', {
      EventSourceCtor: FakeEventSource as unknown as typeof EventSource,
      onConnectionError,
    });
    const es = FakeEventSource.instances[0];

    // Native error events carry no `.data` — dispatch with `undefined`.
    es.dispatch('error', undefined);
    expect(onConnectionError).toHaveBeenCalledTimes(1);
    // Iterator stays open — page shell decides whether to reconnect.
    expect(es.closed).toBe(false);

    // Explicitly close so the iterator drains.
    source.close();
    const events = await drain(source);
    expect(events).toEqual([]);
  });

  it('.close() terminates the iterator without an end event', async () => {
    FakeEventSource.instances = [];
    const source = openReadingSSESource('reading-4', {
      EventSourceCtor: FakeEventSource as unknown as typeof EventSource,
    });
    const es = FakeEventSource.instances[0];

    es.dispatch('subtitle', JSON.stringify({ text: '잠깐만', audio_offset_ms: 0 }));
    source.close();

    const events = await drain(source);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('subtitle');
    expect(es.closed).toBe(true);
  });
});
