import { useNavigate } from 'react-router-dom';
import type { ThreadSummary } from '../../types';

interface Props { thread: ThreadSummary; }

function SenderAvatar({ name, email }: { name?: string | null; email?: string }) {
  const letter = (name ?? email ?? '?')[0].toUpperCase();
  const colors = ['from-violet-500 to-indigo-500', 'from-cyan-500 to-blue-500', 'from-rose-500 to-pink-500', 'from-amber-500 to-orange-500', 'from-emerald-500 to-teal-500'];
  const idx = (name ?? email ?? '').charCodeAt(0) % colors.length;
  return (
    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${colors[idx]} flex items-center justify-center text-xs font-semibold text-white shrink-0`}>
      {letter}
    </div>
  );
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)   return 'now';
  if (m < 60)  return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7)   return `${d}d`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function ThreadRow({ thread }: Props) {
  const navigate = useNavigate();
  const sender = thread.participants?.find(p => p.role === 'sender');
  const time   = thread.last_message_at ? timeAgo(thread.last_message_at) : '';

  return (
    <div
      role="listitem"
      className={`glass-row px-4 py-3.5 group ${thread.is_unread ? 'font-medium' : 'font-normal'}`}
      onClick={() => navigate(`/threads/${thread.id}`)}
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && navigate(`/threads/${thread.id}`)}
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <SenderAvatar name={sender?.name} email={sender?.email} />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <p className={`text-sm truncate ${thread.is_unread ? 'font-semibold text-slate-100' : 'font-medium text-slate-300'}`}>
              {sender?.name ?? sender?.email ?? 'Unknown'}
            </p>
            <span className="text-[11px] text-slate-600 shrink-0">{time}</span>
          </div>

          <p className={`text-xs truncate mb-1.5 ${thread.is_unread ? 'text-slate-300' : 'text-slate-500'}`}>
            {thread.subject ?? '(no subject)'}
          </p>

          {thread.snippet && (
            <p className="text-xs text-slate-600 truncate">{thread.snippet}</p>
          )}

          {/* Chips */}
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {thread.requires_reply && (
              <span className="badge badge-urgent">
                <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" /></svg>
                Reply needed
              </span>
            )}
            {thread.draft_status === 'pending_review' && (
              <span className="badge bg-violet-500/15 text-violet-400 ring-1 ring-violet-500/30">
                <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" /></svg>
                Draft ready
              </span>
            )}
            {thread.is_unread && (
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shrink-0" aria-label="Unread" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
