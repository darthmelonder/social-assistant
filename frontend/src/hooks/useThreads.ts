import { useQuery } from '@tanstack/react-query';
import { listThreads } from '../api/threads';
import type { ThreadListParams } from '../api/threads';

export function useThreads(params: ThreadListParams = {}) {
  return useQuery({
    queryKey: ['threads', params],
    queryFn: () => listThreads(params),
  });
}
