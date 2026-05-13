import { useMutation } from '@tanstack/react-query';
import { updateDraft } from '../api/drafts';
import type { Draft, DraftUpdatePayload } from '../types';

export function useDraft(draftId: string, onSuccess: (draft: Draft) => void) {
  return useMutation({
    mutationFn: (payload: DraftUpdatePayload) => updateDraft(draftId, payload),
    onSuccess: data => onSuccess(data as unknown as Draft),
  });
}
