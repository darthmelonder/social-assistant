import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import AnalysisSummary from './AnalysisSummary';
import type { Analysis } from '../../types';

function makeAnalysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    id: 'a1',
    priority: 'important',
    priority_confidence: 0.85,
    summary: 'Alice needs feedback by Thursday.',
    action_items: [],
    requires_reply: true,
    sentiment: 'neutral',
    ...overrides,
  };
}

describe('AnalysisSummary', () => {
  it('renders the priority label', () => {
    render(<AnalysisSummary analysis={makeAnalysis({ priority: 'urgent' })} />);
    expect(screen.getByText('Urgent')).toBeInTheDocument();
  });

  it('renders the summary text', () => {
    render(<AnalysisSummary analysis={makeAnalysis({ summary: 'Review the proposal.' })} />);
    expect(screen.getByText('Review the proposal.')).toBeInTheDocument();
  });

  it('shows Reply needed badge when requires_reply', () => {
    render(<AnalysisSummary analysis={makeAnalysis({ requires_reply: true })} />);
    expect(screen.getByText('Reply needed')).toBeInTheDocument();
  });

  it('does not show Reply needed when not required', () => {
    render(<AnalysisSummary analysis={makeAnalysis({ requires_reply: false })} />);
    expect(screen.queryByText('Reply needed')).not.toBeInTheDocument();
  });

  it('renders action items', () => {
    render(
      <AnalysisSummary
        analysis={makeAnalysis({
          action_items: [
            { description: 'Send report', due_date_hint: 'Friday', assignee_hint: null },
          ],
        })}
      />,
    );
    expect(screen.getByText('Send report')).toBeInTheDocument();
    expect(screen.getByText('(Friday)')).toBeInTheDocument();
  });

  it('does not show action items section when empty', () => {
    render(<AnalysisSummary analysis={makeAnalysis({ action_items: [] })} />);
    expect(screen.queryByText('Action items')).not.toBeInTheDocument();
  });

  it('shows sentiment label', () => {
    render(<AnalysisSummary analysis={makeAnalysis({ sentiment: 'positive' })} />);
    expect(screen.getByText('positive')).toBeInTheDocument();
  });
});
