import { useState } from 'react';
import { useDraft } from '../../hooks/useDraft';
import type { Draft } from '../../types';

interface Props {
  draft: Draft;
  onUpdate: (updated: Draft) => void;
}

export default function DraftReview({ draft, onUpdate }: Props) {
  const [body, setBody] = useState(draft.body_plain);
  const [copied, setCopied] = useState(false);
  const { mutate, isPending } = useDraft(draft.id, onUpdate as Parameters<typeof useDraft>[1]);

  if (draft.status !== 'pending_review') {
    return (
      <p className="text-sm text-gray-500 italic">
        Draft {draft.status}.
      </p>
    );
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(body);
    } catch {
      // Clipboard unavailable in non-secure contexts — copy flow still proceeds
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    const edited = body !== draft.body_plain ? body : undefined;
    mutate({ status: 'copied', user_edited_body: edited });
  }

  return (
    <div className="space-y-3">
      {draft.subject_line && (
        <p className="text-sm text-gray-600">
          <span className="font-medium">Subject:</span> {draft.subject_line}
        </p>
      )}

      <textarea
        aria-label="Draft reply"
        className="w-full border border-gray-200 rounded-lg p-3 text-sm text-gray-800 min-h-48 resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
        value={body}
        onChange={e => setBody(e.target.value)}
      />

      {draft.tone_used && (
        <p className="text-xs text-gray-400">Tone: {draft.tone_used}</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => mutate({ status: 'approved' })}
          disabled={isPending}
          className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
        >
          Approve
        </button>
        <button
          onClick={handleCopy}
          disabled={isPending}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
        >
          {copied ? 'Copied!' : 'Copy to clipboard'}
        </button>
        <button
          onClick={() => mutate({ status: 'rejected' })}
          disabled={isPending}
          className="px-3 py-1.5 text-gray-600 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}
