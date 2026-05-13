import type { Analysis, Priority } from '../../types';

const PRIORITY_STYLE: Record<Priority, string> = {
  urgent:    'bg-red-100 text-red-800',
  important: 'bg-orange-100 text-orange-800',
  maybe:     'bg-yellow-100 text-yellow-800',
  skip:      'bg-gray-100 text-gray-600',
};

interface Props {
  analysis: Analysis;
}

export default function AnalysisSummary({ analysis }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${PRIORITY_STYLE[analysis.priority]}`}>
          {analysis.priority.charAt(0).toUpperCase() + analysis.priority.slice(1)}
        </span>
        {analysis.requires_reply && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
            Reply needed
          </span>
        )}
        {analysis.sentiment && (
          <span className="text-xs text-gray-500">{analysis.sentiment}</span>
        )}
      </div>

      <p className="text-sm text-gray-700 leading-relaxed">{analysis.summary}</p>

      {analysis.action_items.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Action items
          </p>
          <ul className="space-y-1">
            {analysis.action_items.map((item, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2">
                <span className="text-gray-400 shrink-0">•</span>
                <span>
                  {item.description}
                  {item.due_date_hint && (
                    <span className="text-gray-400 ml-1">({item.due_date_hint})</span>
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
