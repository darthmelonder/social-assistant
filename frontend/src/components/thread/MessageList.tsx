import type { Message } from '../../types';

interface Props { messages: Message[]; }

function Avatar({ name, email, isSelf }: { name?: string | null; email: string; isSelf: boolean }) {
  const letter = (name ?? email)[0].toUpperCase();
  return (
    <div
      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold text-white shrink-0 ${
        isSelf
          ? 'bg-gradient-to-br from-violet-500 to-cyan-500'
          : 'bg-gradient-to-br from-slate-600 to-slate-700 border border-white/10'
      }`}
      aria-hidden="true"
    >
      {letter}
    </div>
  );
}

export default function MessageList({ messages }: Props) {
  return (
    <div className="space-y-3">
      {messages.map(msg => (
        <article
          key={msg.id}
          className={`glass rounded-2xl p-4 ${msg.is_sent_by_user ? 'border-violet-500/20' : ''}`}
        >
          <header className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <Avatar name={msg.from_name} email={msg.from_email} isSelf={msg.is_sent_by_user} />
              <div>
                <p className="text-sm font-semibold text-slate-200 leading-tight">
                  {msg.from_name ?? msg.from_email}
                  {msg.is_sent_by_user && (
                    <span className="ml-1.5 text-[10px] font-medium text-violet-400 bg-violet-500/15 px-1.5 py-0.5 rounded-md">you</span>
                  )}
                </p>
                <p className="text-[11px] text-slate-600 leading-tight">{msg.from_email}</p>
              </div>
            </div>
            <time className="text-[11px] text-slate-600 shrink-0 mt-0.5">
              {new Date(msg.internal_date).toLocaleString(undefined, {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
              })}
            </time>
          </header>

          <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed pl-9">
            {msg.body_plain ?? msg.snippet ?? '(empty)'}
          </div>

          {msg.has_attachments && (
            <div className="flex items-center gap-1.5 mt-3 pl-9">
              <svg className="w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
              </svg>
              <span className="text-xs text-slate-500">Has attachments</span>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
