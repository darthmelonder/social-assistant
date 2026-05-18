import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import AnalysisSummary from '../components/thread/AnalysisSummary';
import MessageList from '../components/thread/MessageList';
import DraftReview from '../components/draft/DraftReview';
import ErrorMessage from '../components/common/ErrorMessage';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useThread } from '../hooks/useThread';
import type { Draft } from '../types';

export default function ThreadPage() {
  const { id }  = useParams<{ id: string }>();
  const { data, isLoading, error } = useThread(id ?? '');
  const [draft, setDraft] = useState<Draft | null>(null);

  if (isLoading) return <LoadingSpinner />;
  if (error || !data) return <ErrorMessage message="Thread not found." />;

  const activeDraft = draft ?? data.draft;

  return (
    <div className="flex flex-col min-h-screen">

      {/* Top bar */}
      <div className="sticky top-0 z-10 px-6 py-3 border-b border-white/[0.06] bg-[#080c1a]/80 backdrop-blur-xl flex items-center gap-3">
        <Link
          to="/"
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-200 transition-colors duration-150 cursor-pointer"
          aria-label="Back to inbox"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Inbox
        </Link>
        <span className="text-slate-700" aria-hidden="true">/</span>
        <h1 className="text-sm font-semibold text-slate-200 truncate flex-1">
          {data.subject ?? '(no subject)'}
        </h1>
      </div>

      {/* Split-pane */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-0 divide-x divide-white/[0.06]">

        {/* ── Left: Thread messages ── */}
        <div className="px-6 py-5 overflow-y-auto">
          <MessageList messages={data.messages} />
        </div>

        {/* ── Right: AI panel ── */}
        <div className="px-5 py-5 space-y-4 overflow-y-auto lg:max-h-screen lg:sticky lg:top-[53px]">

          {data.analysis && (
            <section className="glass rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <svg className="w-3.5 h-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                <h2 className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest">AI Summary</h2>
              </div>
              <AnalysisSummary analysis={data.analysis} />
            </section>
          )}

          {activeDraft && (
            <section className="glass rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <svg className="w-3.5 h-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                </svg>
                <h2 className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest">Draft Reply</h2>
              </div>
              <DraftReview draft={activeDraft} onUpdate={updated => setDraft(updated)} />
            </section>
          )}

          {!data.analysis && !activeDraft && (
            <div className="glass rounded-2xl p-6 text-center">
              <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mx-auto mb-3" aria-hidden="true" />
              <p className="text-sm text-slate-500">Triage in progress…</p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
