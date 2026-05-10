import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listDrafts, requestDraft, updateDraft } from './drafts';
import * as client from './client';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
const mockFetch = vi.mocked(client.apiFetch);

beforeEach(() => mockFetch.mockReset());

describe('listDrafts', () => {
  it('calls GET /api/v1/threads/:id/drafts', async () => {
    mockFetch.mockResolvedValueOnce([]);
    await listDrafts('thr-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads/thr-1/drafts');
  });
});

describe('requestDraft', () => {
  it('calls POST /api/v1/threads/:id/drafts', async () => {
    mockFetch.mockResolvedValueOnce({ job_id: 'j1' });
    await requestDraft('thr-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/threads/thr-1/drafts', { method: 'POST' });
  });
});

describe('updateDraft', () => {
  it('calls PATCH /api/v1/drafts/:id with status', async () => {
    mockFetch.mockResolvedValueOnce({});
    await updateDraft('draft-1', { status: 'approved' });
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/drafts/draft-1', {
      method: 'PATCH',
      body: JSON.stringify({ status: 'approved' }),
    });
  });

  it('includes user_edited_body when provided', async () => {
    mockFetch.mockResolvedValueOnce({});
    await updateDraft('draft-1', { status: 'copied', user_edited_body: 'My edit' });
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.user_edited_body).toBe('My edit');
  });

  it('includes feedback_note when provided', async () => {
    mockFetch.mockResolvedValueOnce({});
    await updateDraft('draft-1', { status: 'rejected', feedback_note: 'Too formal' });
    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string);
    expect(body.feedback_note).toBe('Too formal');
  });
});
