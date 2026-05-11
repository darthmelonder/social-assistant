import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import PriorityBand from './PriorityBand';
import type { ThreadSummary } from '../../types';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

function makeThread(id: string): ThreadSummary {
  return {
    id,
    subject: `Thread ${id}`,
    snippet: 'snippet',
    last_message_at: null,
    is_unread: false,
    participants: [],
    priority: 'urgent',
    summary: null,
    action_items: [],
    requires_reply: false,
    draft_status: null,
  };
}

function renderBand(threads: ThreadSummary[], defaultOpen = true) {
  return render(
    <MemoryRouter>
      <PriorityBand priority="urgent" threads={threads} defaultOpen={defaultOpen} />
    </MemoryRouter>,
  );
}

describe('PriorityBand', () => {
  it('renders the priority label', () => {
    renderBand([]);
    expect(screen.getByText('Urgent')).toBeInTheDocument();
  });

  it('shows thread count', () => {
    renderBand([makeThread('t1'), makeThread('t2')]);
    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('shows threads when open by default', () => {
    renderBand([makeThread('t1')], true);
    expect(screen.getByText('Thread t1')).toBeInTheDocument();
  });

  it('hides threads when closed by default', () => {
    renderBand([makeThread('t1')], false);
    expect(screen.queryByText('Thread t1')).not.toBeInTheDocument();
  });

  it('toggles open on button click', async () => {
    const user = userEvent.setup();
    renderBand([makeThread('t1')], false);
    expect(screen.queryByText('Thread t1')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button'));
    expect(screen.getByText('Thread t1')).toBeInTheDocument();
  });

  it('shows empty message when open with no threads', () => {
    renderBand([], true);
    expect(screen.getByText('No urgent threads')).toBeInTheDocument();
  });
});
