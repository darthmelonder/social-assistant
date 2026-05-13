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
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useThread(id ?? '');
  const [draft, setDraft] = useState<Draft | null>(null);

  if (isLoading) return <LoadingSpinner />;
  if (error || !data) return <ErrorMessage message="Thread not found." />;

  // Use local draft state after updates; fall back to server-fetched draft
  const activeDraft = draft ?? data.draft;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-900">
          ← Inbox
        </Link>
      </div>

      <h1 className="text-xl font-semibold text-gray-900">
        {data.subject ?? '(no subject)'}
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Messages column */}
        <div className="lg:col-span-2">
          <MessageList messages={data.messages} />
        </div>

        {/* Analysis + Draft panel */}
        <div className="space-y-6">
          {data.analysis && (
            <section className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
                Summary
              </h2>
              <AnalysisSummary analysis={data.analysis} />
            </section>
          )}

          {activeDraft && (
            <section className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
                Draft reply
              </h2>
              <DraftReview
                draft={activeDraft}
                onUpdate={updated => setDraft(updated)}
              />
            </section>
          )}

          {!data.analysis && !activeDraft && (
            <p className="text-sm text-gray-400 text-center py-4">
              Triage in progress…
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
