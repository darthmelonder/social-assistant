import type { Message } from '../../types';

interface Props {
  messages: Message[];
}

export default function MessageList({ messages }: Props) {
  return (
    <div className="space-y-4">
      {messages.map(msg => (
        <article key={msg.id} className="bg-white rounded-lg border border-gray-200 p-4">
          <header className="flex items-start justify-between mb-3">
            <div>
              <p className="text-sm font-medium text-gray-900">
                {msg.from_name ?? msg.from_email}
                {msg.is_sent_by_user && (
                  <span className="ml-2 text-xs text-gray-400 font-normal">(you)</span>
                )}
              </p>
              <p className="text-xs text-gray-500">{msg.from_email}</p>
            </div>
            <time className="text-xs text-gray-400 shrink-0">
              {new Date(msg.internal_date).toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </time>
          </header>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {msg.body_plain ?? msg.snippet ?? '(empty)'}
          </div>
          {msg.has_attachments && (
            <p className="mt-2 text-xs text-gray-400">📎 Has attachments</p>
          )}
        </article>
      ))}
    </div>
  );
}
