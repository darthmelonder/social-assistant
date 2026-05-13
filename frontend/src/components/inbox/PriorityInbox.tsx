import ErrorMessage from '../common/ErrorMessage';
import LoadingSpinner from '../common/LoadingSpinner';
import PriorityBand from './PriorityBand';
import { useThreads } from '../../hooks/useThreads';
import type { Priority, ThreadSummary } from '../../types';

const PRIORITIES: Priority[] = ['urgent', 'important', 'maybe', 'skip'];

export default function PriorityInbox() {
  const { data, isLoading, error } = useThreads();

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Failed to load inbox. Please refresh." />;

  const threads = data?.threads ?? [];

  const byPriority = PRIORITIES.reduce<Record<Priority, ThreadSummary[]>>(
    (acc, p) => ({ ...acc, [p]: threads.filter(t => t.priority === p) }),
    { urgent: [], important: [], maybe: [], skip: [] },
  );

  // Also bucket unclassified threads (no analysis yet) into their own section
  const unclassified = threads.filter(t => t.priority === null);

  return (
    <div className="space-y-3">
      {PRIORITIES.map(p => (
        <PriorityBand
          key={p}
          priority={p}
          threads={byPriority[p]}
          defaultOpen={p === 'urgent' || p === 'important'}
        />
      ))}
      {unclassified.length > 0 && (
        <section className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <p className="px-4 py-3 text-sm text-gray-500 font-medium">
            Classifying… ({unclassified.length})
          </p>
        </section>
      )}
    </div>
  );
}
