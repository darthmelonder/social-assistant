import { apiFetch } from './client';
import type { ThreadListResponse, ThreadDetail } from '../types';

export interface ThreadListParams {
  priority?: string;
  limit?: number;
  after_id?: string;
  connection_id?: string;
}

export async function listThreads(params: ThreadListParams = {}): Promise<ThreadListResponse> {
  const qs = new URLSearchParams();
  if (params.priority) qs.set('priority', params.priority);
  if (params.limit != null) qs.set('limit', String(params.limit));
  if (params.after_id) qs.set('after_id', params.after_id);
  if (params.connection_id) qs.set('connection_id', params.connection_id);
  const query = qs.toString();
  return apiFetch(`/api/v1/threads${query ? `?${query}` : ''}`);
}

export async function getThread(id: string): Promise<ThreadDetail> {
  return apiFetch(`/api/v1/threads/${id}`);
}

export async function retriageThread(id: string): Promise<{ job_id: string; message: string }> {
  return apiFetch(`/api/v1/threads/${id}/retriage`, { method: 'POST' });
}

export async function patchThreadPriority(
  id: string,
  priority: string,
): Promise<{ id: string; priority_override: string }> {
  return apiFetch(`/api/v1/threads/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ priority_override: priority }),
  });
}
