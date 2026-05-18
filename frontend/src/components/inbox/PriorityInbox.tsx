import ErrorMessage from '../common/ErrorMessage';
import LoadingSpinner from '../common/LoadingSpinner';
import PriorityBand from './PriorityBand';
import { useThreads } from '../../hooks/useThreads';
import type { Priority, ThreadSummary } from '../../types';

const PRIORITIES: Priority[] = ['urgent', 'important', 'maybe', 'skip'];

export default function PriorityInbox() {
  const { data, isLoading, error } = useThreads();

  if (isLoading) return <LoadingSpinner />;
  if (error)     return <ErrorMessage message="Failed to load inbox. Please refresh." />;

  const threads     = data?.threads ?? [];
  const byPriority  = PRIORITIES.reduce<Record<Priority, ThreadSummary[]>>(
    (acc, p) => ({ ...acc, [p]: threads.filter(t => t.priority === p) }),
    { urgent: [], important: [], maybe: [], skip: [] },
  );
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
        <section className="glass rounded-2xl overflow-hidden border-l-2 border-slate-700">
          <div className="flex items-center gap-2.5 px-4 py-3.5">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-600 animate-pulse-slow" aria-hidden="true" />
            <p className="text-sm font-medium text-slate-500">
              Classifying… <span className="text-slate-600">({unclassified.length})</span>
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
