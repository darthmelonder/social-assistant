import { useNavigate } from 'react-router-dom';
import type { ThreadSummary } from '../../types';

interface Props {
  thread: ThreadSummary;
}

export default function ThreadRow({ thread }: Props) {
  const navigate = useNavigate();

  const time = thread.last_message_at
    ? new Date(thread.last_message_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      })
    : '';

  return (
    <div
      role="listitem"
      className={`border-t border-gray-100 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${
        thread.is_unread ? 'font-medium' : 'font-normal'
      }`}
      onClick={() => navigate(`/threads/${thread.id}`)}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-gray-900 truncate">
          {thread.subject ?? '(no subject)'}
        </p>
        <span className="text-xs text-gray-400 shrink-0">{time}</span>
      </div>
      <p className="text-sm text-gray-500 truncate mt-0.5">{thread.snippet}</p>
      <div className="flex gap-1.5 mt-1">
        {thread.requires_reply && (
          <span className="text-xs bg-blue-100 text-blue-700 rounded px-1.5 py-0.5">
            Reply needed
          </span>
        )}
        {thread.draft_status === 'pending_review' && (
          <span className="text-xs bg-green-100 text-green-700 rounded px-1.5 py-0.5">
            Draft ready
          </span>
        )}
      </div>
    </div>
  );
}
