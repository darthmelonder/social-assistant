import type { Analysis, Priority } from '../../types';

const BADGE: Record<Priority, string> = {
  urgent:    'badge-urgent',
  important: 'badge-important',
  maybe:     'badge-maybe',
  skip:      'badge-skip',
};

const SENTIMENT_COLOR: Record<string, string> = {
  positive: 'text-emerald-400',
  neutral:  'text-slate-400',
  negative: 'text-red-400',
  mixed:    'text-amber-400',
};

interface Props { analysis: Analysis; }

export default function AnalysisSummary({ analysis }: Props) {
  return (
    <div className="space-y-4">

      {/* Badges row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`badge ${BADGE[analysis.priority]}`}>
          {analysis.priority.charAt(0).toUpperCase() + analysis.priority.slice(1)}
        </span>
        {analysis.requires_reply && (
          <span className="badge badge-urgent">Reply needed</span>
        )}
        {analysis.sentiment && (
          <span className={`text-xs font-medium ${SENTIMENT_COLOR[analysis.sentiment] ?? 'text-slate-400'}`}>
            {analysis.sentiment}
          </span>
        )}
        {analysis.priority_confidence != null && (
          <span className="text-xs text-slate-600 ml-auto">
            {Math.round(analysis.priority_confidence * 100)}% confident
          </span>
        )}
      </div>

      {/* Summary */}
      <p className="text-sm text-slate-300 leading-relaxed">{analysis.summary}</p>

      {/* Action items */}
      {analysis.action_items.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest mb-2.5">
            Action items
          </p>
          <ul className="space-y-2" role="list">
            {analysis.action_items.map((item, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-violet-500/60 shrink-0" aria-hidden="true" />
                <span className="text-sm text-slate-300 leading-snug">
                  {item.description}
                  {item.due_date_hint && (
                    <span className="ml-1.5 text-xs text-slate-500 bg-white/[0.05] px-1.5 py-0.5 rounded-md">
                      ({item.due_date_hint})
                    </span>
                  )}
                  {item.assignee_hint && (
                    <span className="ml-1 text-xs text-slate-500">→ {item.assignee_hint}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
