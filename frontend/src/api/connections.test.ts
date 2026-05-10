import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listConnections, getConnection, disconnectConnection, triggerSync } from './connections';
import * as client from './client';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
const mockFetch = vi.mocked(client.apiFetch);

beforeEach(() => mockFetch.mockReset());

describe('listConnections', () => {
  it('calls GET /api/v1/connections', async () => {
    mockFetch.mockResolvedValueOnce([]);
    await listConnections();
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/connections');
  });
});

describe('getConnection', () => {
  it('calls GET /api/v1/connections/:id', async () => {
    mockFetch.mockResolvedValueOnce({});
    await getConnection('conn-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/connections/conn-1');
  });
});

describe('disconnectConnection', () => {
  it('calls DELETE /api/v1/connections/:id', async () => {
    mockFetch.mockResolvedValueOnce(null);
    await disconnectConnection('conn-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/connections/conn-1', { method: 'DELETE' });
  });
});

describe('triggerSync', () => {
  it('calls POST /api/v1/connections/:id/sync', async () => {
    mockFetch.mockResolvedValueOnce({ job_id: 'j1' });
    await triggerSync('conn-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/connections/conn-1/sync', { method: 'POST' });
  });
});
