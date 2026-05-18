import PriorityInbox from '../components/inbox/PriorityInbox';
import { useThreads } from '../hooks/useThreads';
import type { Priority } from '../types';

const PRIORITY_ORDER: Priority[] = ['urgent', 'important', 'maybe', 'skip'];

function StatPill({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="glass rounded-xl px-4 py-3 flex flex-col gap-0.5 min-w-[90px]">
      <p className={`text-xl font-bold ${color}`}>{count}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

export default function InboxPage() {
  const { data } = useThreads();
  const threads = data?.threads ?? [];

  const counts = PRIORITY_ORDER.reduce<Record<Priority, number>>(
    (acc, p) => ({ ...acc, [p]: threads.filter(t => t.priority === p).length }),
    { urgent: 0, important: 0, maybe: 0, skip: 0 },
  );
  const draftsReady = threads.filter(t => t.draft_status === 'pending_review').length;

  return (
    <div className="px-6 py-6 max-w-3xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-100 tracking-tight">Inbox</h1>
        <p className="text-sm text-slate-500 mt-0.5">AI-triaged · read-only</p>
      </div>

      {/* Stats strip */}
      {threads.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap" aria-label="Inbox summary">
          <StatPill label="Urgent"    count={counts.urgent}    color="text-red-400" />
          <StatPill label="Important" count={counts.important} color="text-orange-400" />
          <StatPill label="Maybe"     count={counts.maybe}     color="text-yellow-400" />
          {draftsReady > 0 && (
            <StatPill label="Drafts ready" count={draftsReady} color="text-violet-400" />
          )}
        </div>
      )}

      {/* Priority inbox */}
      <PriorityInbox />
    </div>
  );
}
