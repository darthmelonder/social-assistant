import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DraftReview from './DraftReview';
import type { Draft } from '../../types';

vi.mock('../../hooks/useDraft', () => ({
  useDraft: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));

// Clipboard API is not available in jsdom; the component gracefully handles it.

function makeDraft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: 'draft-1',
    subject_line: 'Re: Q2 Report',
    body_plain: 'Hi Alice,\n\nThanks for reaching out.',
    body_html: null,
    tone_used: 'professional',
    status: 'pending_review',
    regeneration_count: 0,
    ...overrides,
  };
}

describe('DraftReview', () => {
  const onUpdate = vi.fn();

  beforeEach(() => {
    onUpdate.mockReset();
  });

  it('renders the draft body in a textarea', () => {
    render(<DraftReview draft={makeDraft()} onUpdate={onUpdate} />);
    expect(screen.getByRole('textbox', { name: /draft reply/i })).toHaveValue(
      'Hi Alice,\n\nThanks for reaching out.',
    );
  });

  it('renders the subject line', () => {
    render(<DraftReview draft={makeDraft()} onUpdate={onUpdate} />);
    expect(screen.getByText(/Re: Q2 Report/)).toBeInTheDocument();
  });

  it('renders Approve, Copy, and Reject buttons', () => {
    render(<DraftReview draft={makeDraft()} onUpdate={onUpdate} />);
    expect(screen.getByText('Approve')).toBeInTheDocument();
    expect(screen.getByText('Copy to clipboard')).toBeInTheDocument();
    expect(screen.getByText('Reject')).toBeInTheDocument();
  });

  it('calls mutate with approved status on Approve click', async () => {
    const mutate = vi.fn();
    const { useDraft } = await import('../../hooks/useDraft');
    vi.mocked(useDraft).mockReturnValue({ mutate, isPending: false } as ReturnType<typeof useDraft>);

    const user = userEvent.setup();
    render(<DraftReview draft={makeDraft()} onUpdate={onUpdate} />);
    await user.click(screen.getByText('Approve'));
    expect(mutate).toHaveBeenCalledWith({ status: 'approved' });
  });

  it('calls mutate with rejected status on Reject click', async () => {
    const mutate = vi.fn();
    const { useDraft } = await import('../../hooks/useDraft');
    vi.mocked(useDraft).mockReturnValue({ mutate, isPending: false } as ReturnType<typeof useDraft>);

    const user = userEvent.setup();
    render(<DraftReview draft={makeDraft()} onUpdate={onUpdate} />);
    await user.click(screen.getByText('Reject'));
    expect(mutate).toHaveBeenCalledWith({ status: 'rejected' });
  });

  it('shows Copied! feedback and calls mutate on Copy click', async () => {
    const mutate = vi.fn();
    const { useDraft } = await import('../../hooks/useDraft');
    vi.mocked(useDraft).mockReturnValue({ mutate, isPending: false } as ReturnType<typeof useDraft>);

    const user = userEvent.setup();
    render(<DraftReview draft={makeDraft()} onUpdate={onUpdate} />);
    await user.click(screen.getByText('Copy to clipboard'));

    // findByText waits for the async handleCopy to complete and state to update
    expect(await screen.findByText('Copied!')).toBeInTheDocument();
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ status: 'copied' }));
  });

  it('shows "Draft approved." when status is approved', () => {
    render(<DraftReview draft={makeDraft({ status: 'approved' })} onUpdate={onUpdate} />);
    expect(screen.getByText('Draft approved.')).toBeInTheDocument();
  });

  it('shows tone when provided', () => {
    render(<DraftReview draft={makeDraft({ tone_used: 'casual and friendly' })} onUpdate={onUpdate} />);
    expect(screen.getByText(/casual and friendly/)).toBeInTheDocument();
  });

  it('does not show subject when null', () => {
    render(<DraftReview draft={makeDraft({ subject_line: null })} onUpdate={onUpdate} />);
    expect(screen.queryByText(/Subject:/)).not.toBeInTheDocument();
  });
});
