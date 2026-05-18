import { useState } from 'react';
import { useDraft } from '../../hooks/useDraft';
import type { Draft } from '../../types';

interface Props {
  draft: Draft;
  onUpdate: (updated: Draft) => void;
}

const TONES = ['Professional', 'Warm', 'Direct', 'Brief'];

export default function DraftReview({ draft, onUpdate }: Props) {
  const [body, setBody]         = useState(draft.body_plain);
  const [copied, setCopied]     = useState(false);
  const [activeTone, setTone]   = useState<string | null>(draft.tone_used ?? null);
  const { mutate, isPending }   = useDraft(draft.id, onUpdate as Parameters<typeof useDraft>[1]);

  if (draft.status !== 'pending_review') {
    return (
      <p className="text-sm text-slate-500 italic">
        Draft {draft.status}.
      </p>
    );
  }

  async function handleCopy() {
    try { await navigator.clipboard.writeText(body); } catch { /* non-secure context */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    const edited = body !== draft.body_plain ? body : undefined;
    mutate({ status: 'copied', user_edited_body: edited });
  }

  return (
    <div className="space-y-4">

      {/* Subject */}
      {draft.subject_line && (
        <div className="px-3 py-2 rounded-xl bg-white/[0.04] border border-white/[0.06]">
          <p className="text-[11px] text-slate-500 uppercase tracking-widest mb-0.5">Subject</p>
          <p className="text-sm text-slate-200 font-medium">{draft.subject_line}</p>
        </div>
      )}

      {/* Tone chips */}
      <div>
        <p className="text-[11px] text-slate-500 uppercase tracking-widest mb-2">Tone</p>
        <div className="flex gap-1.5 flex-wrap">
          {TONES.map(t => (
            <button
              key={t}
              onClick={() => setTone(prev => prev === t ? null : t)}
              className={`tone-chip ${activeTone === t ? 'tone-chip-active' : ''}`}
            >
              {t}
            </button>
          ))}
        </div>
        {draft.tone_used && (
          <p className="text-xs text-slate-600 mt-1.5">Generated as: {draft.tone_used}</p>
        )}
      </div>

      {/* Editable body */}
      <textarea
        aria-label="Draft reply"
        className="w-full rounded-xl p-3.5 text-sm text-slate-200 leading-relaxed min-h-48 resize-y
                   bg-white/[0.04] border border-white/[0.08] placeholder-slate-600
                   focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20
                   transition-colors duration-150"
        value={body}
        onChange={e => setBody(e.target.value)}
        placeholder="Draft body…"
      />

      {/* Character count */}
      <p className="text-[11px] text-slate-600 text-right -mt-2">{body.length} chars</p>

      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => mutate({ status: 'approved' })} disabled={isPending} className="btn-approve">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          Approve
        </button>
        <button onClick={handleCopy} disabled={isPending} className="btn-primary py-2 px-4">
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
              </svg>
              Copy to clipboard
            </>
          )}
        </button>
        <button onClick={() => mutate({ status: 'rejected' })} disabled={isPending} className="btn-danger">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          Reject
        </button>
      </div>
    </div>
  );
}
