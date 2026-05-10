import { apiFetch } from './client';
import type { DraftListItem, DraftUpdatePayload } from '../types';

export async function listDrafts(threadId: string): Promise<DraftListItem[]> {
  return apiFetch(`/api/v1/threads/${threadId}/drafts`);
}

export async function requestDraft(threadId: string): Promise<{ job_id: string }> {
  return apiFetch(`/api/v1/threads/${threadId}/drafts`, { method: 'POST' });
}

export async function updateDraft(
  draftId: string,
  payload: DraftUpdatePayload,
): Promise<DraftListItem> {
  return apiFetch(`/api/v1/drafts/${draftId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
