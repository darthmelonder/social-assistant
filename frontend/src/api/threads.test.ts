import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listThreads, getThread, retriageThread, patchThreadPriority } from './threads';
import * as client from './client';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
const mockFetch = vi.mocked(client.apiFetch);

beforeEach(() => mockFetch.mockReset());

const EMPTY_LIST = { threads: [], next_cursor: null };

describe('listThreads', () => {
  it('calls /api/v1/threads with no params', async () => {
    mockFetch.mockResolvedValueOnce(EMPTY_LIST);
    await listThreads();
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads');
  });

  it('adds priority query param', async () => {
    mockFetch.mockResolvedValueOnce(EMPTY_LIST);
    await listThreads({ priority: 'urgent' });
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads?priority=urgent');
  });

  it('adds limit query param', async () => {
    mockFetch.mockResolvedValueOnce(EMPTY_LIST);
    await listThreads({ limit: 20 });
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads?limit=20');
  });

  it('adds after_id cursor param', async () => {
    mockFetch.mockResolvedValueOnce(EMPTY_LIST);
    await listThreads({ after_id: 'cursor-uuid' });
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads?after_id=cursor-uuid');
  });

  it('combines multiple params', async () => {
    mockFetch.mockResolvedValueOnce(EMPTY_LIST);
    await listThreads({ priority: 'important', limit: 10 });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('priority=important');
    expect(url).toContain('limit=10');
  });
});

describe('getThread', () => {
  it('calls /api/v1/threads/:id', async () => {
    mockFetch.mockResolvedValueOnce({});
    await getThread('thread-123');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads/thread-123');
  });
});

describe('retriageThread', () => {
  it('calls POST /api/v1/threads/:id/retriage', async () => {
    mockFetch.mockResolvedValueOnce({ job_id: 'j1', message: 'queued' });
    await retriageThread('thr-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads/thr-1/retriage', { method: 'POST' });
  });
});

describe('patchThreadPriority', () => {
  it('calls PATCH /api/v1/threads/:id with priority body', async () => {
    mockFetch.mockResolvedValueOnce({ id: 'thr-1', priority_override: 'maybe' });
    await patchThreadPriority('thr-1', 'maybe');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads/thr-1', {
      method: 'PATCH',
      body: JSON.stringify({ priority_override: 'maybe' }),
    });
  });
});
