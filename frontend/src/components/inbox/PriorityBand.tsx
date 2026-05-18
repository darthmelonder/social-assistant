import { useState } from 'react';
import type { Priority, ThreadSummary } from '../../types';
import ThreadRow from './ThreadRow';

const CONFIG: Record<Priority, { label: string; dot: string; badge: string; band: string }> = {
  urgent:    { label: 'Urgent',    dot: 'dot-urgent',    badge: 'badge-urgent',    band: 'band-urgent'    },
  important: { label: 'Important', dot: 'dot-important', badge: 'badge-important', band: 'band-important' },
  maybe:     { label: 'Maybe',     dot: 'dot-maybe',     badge: 'badge-maybe',     band: 'band-maybe'     },
  skip:      { label: 'Skip',      dot: 'dot-skip',      badge: 'badge-skip',      band: 'band-skip'      },
};

interface Props {
  priority: Priority;
  threads: ThreadSummary[];
  defaultOpen?: boolean;
}

export default function PriorityBand({ priority, threads, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const { label, dot, badge, band } = CONFIG[priority];

  return (
    <section aria-label={label} className={`glass rounded-2xl overflow-hidden ${band}`}>
      <button
        className="w-full flex items-center justify-between px-4 py-3.5 text-left cursor-pointer
                   hover:bg-white/[0.04] transition-colors duration-150 focus-visible:outline-none
                   focus-visible:ring-2 focus-visible:ring-violet-500/50"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <div className="flex items-center gap-2.5">
          <span className={dot} aria-hidden="true" />
          <span className="font-semibold text-slate-200 text-sm">{label}</span>
          <span className={`badge ${badge}`}>({threads.length})</span>
        </div>
        <svg
          className={`w-4 h-4 text-slate-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {open && (
        <div role="list" className="animate-slide-down">
          {threads.length === 0 ? (
            <p className="px-4 py-4 text-sm text-slate-600 border-t border-white/[0.06] text-center">
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
