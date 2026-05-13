import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import ThreadRow from './ThreadRow';
import type { ThreadSummary } from '../../types';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

function makeThread(overrides: Partial<ThreadSummary> = {}): ThreadSummary {
  return {
    id: 'thr-1',
    subject: 'Test Subject',
    snippet: 'Test snippet text',
    last_message_at: '2026-01-15T10:00:00Z',
    is_unread: false,
    participants: [],
    priority: 'important',
    summary: 'Summary',
    action_items: [],
    requires_reply: false,
    draft_status: null,
    ...overrides,
  };
}

function renderRow(thread: ThreadSummary) {
  return render(
    <MemoryRouter>
      <ThreadRow thread={thread} />
    </MemoryRouter>,
  );
}

describe('ThreadRow', () => {
  it('renders the subject', () => {
    renderRow(makeThread({ subject: 'My Important Email' }));
    expect(screen.getByText('My Important Email')).toBeInTheDocument();
  });

  it('renders (no subject) when subject is null', () => {
    renderRow(makeThread({ subject: null }));
    expect(screen.getByText('(no subject)')).toBeInTheDocument();
  });

  it('renders the snippet', () => {
    renderRow(makeThread({ snippet: 'Please review this.' }));
    expect(screen.getByText('Please review this.')).toBeInTheDocument();
  });

  it('shows Reply needed badge when requires_reply is true', () => {
    renderRow(makeThread({ requires_reply: true }));
    expect(screen.getByText('Reply needed')).toBeInTheDocument();
  });

  it('does not show Reply needed badge when requires_reply is false', () => {
    renderRow(makeThread({ requires_reply: false }));
    expect(screen.queryByText('Reply needed')).not.toBeInTheDocument();
  });

  it('shows Draft ready badge when draft_status is pending_review', () => {
    renderRow(makeThread({ draft_status: 'pending_review' }));
    expect(screen.getByText('Draft ready')).toBeInTheDocument();
  });

  it('does not show Draft ready for other draft statuses', () => {
    renderRow(makeThread({ draft_status: 'approved' }));
    expect(screen.queryByText('Draft ready')).not.toBeInTheDocument();
  });

  it('applies bold styling when unread', () => {
    const { container } = renderRow(makeThread({ is_unread: true }));
    expect(container.firstChild).toHaveClass('font-medium');
  });

  it('applies normal weight when read', () => {
    const { container } = renderRow(makeThread({ is_unread: false }));
    expect(container.firstChild).toHaveClass('font-normal');
  });
});
