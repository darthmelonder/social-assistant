import { useQuery } from '@tanstack/react-query';
import { getThread } from '../api/threads';

export function useThread(id: string) {
  return useQuery({
    queryKey: ['thread', id],
    queryFn: () => getThread(id),
    enabled: !!id,
  });
}
