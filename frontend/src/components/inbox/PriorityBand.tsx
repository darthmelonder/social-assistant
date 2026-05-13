import { useState } from 'react';
import type { Priority, ThreadSummary } from '../../types';
import ThreadRow from './ThreadRow';

const CONFIG: Record<Priority, { label: string; dot: string }> = {
  urgent:    { label: 'Urgent',    dot: 'bg-red-500'    },
  important: { label: 'Important', dot: 'bg-orange-500' },
  maybe:     { label: 'Maybe',     dot: 'bg-yellow-500' },
  skip:      { label: 'Skip',      dot: 'bg-gray-400'   },
};

interface Props {
  priority: Priority;
  threads: ThreadSummary[];
  defaultOpen?: boolean;
}

export default function PriorityBand({ priority, threads, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const { label, dot } = CONFIG[priority];

  return (
    <section
      aria-label={label}
      className="bg-white rounded-lg border border-gray-200 overflow-hidden"
    >
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />
          <span className="font-medium text-gray-900 text-sm">{label}</span>
          <span className="text-xs text-gray-400">({threads.length})</span>
        </div>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div role="list">
          {threads.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-400 border-t border-gray-100">
              No {label.toLowerCase()} threads
            </p>
          ) : (
            threads.map(t => <ThreadRow key={t.id} thread={t} />)
          )}
        </div>
      )}
    </section>
  );
}
