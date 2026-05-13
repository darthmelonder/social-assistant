import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ConnectGmail from './ConnectGmail';

vi.mock('../../api/auth', () => ({
  getAuthorizeUrl: vi.fn(),
}));

describe('ConnectGmail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Connect Gmail button', () => {
    render(<ConnectGmail />);
    expect(screen.getByText('Connect Gmail')).toBeInTheDocument();
  });

  it('renders the page heading', () => {
    render(<ConnectGmail />);
    expect(screen.getByText('Social Assistant')).toBeInTheDocument();
  });

  it('shows Redirecting… while loading', async () => {
    const { getAuthorizeUrl } = await import('../../api/auth');
    vi.mocked(getAuthorizeUrl).mockImplementation(
      () => new Promise(() => {}), // never resolves
    );

    const user = userEvent.setup();
    render(<ConnectGmail />);
    await user.click(screen.getByText('Connect Gmail'));
    expect(screen.getByText('Redirecting…')).toBeInTheDocument();
  });

  it('shows error message when getAuthorizeUrl fails', async () => {
    const { getAuthorizeUrl } = await import('../../api/auth');
    vi.mocked(getAuthorizeUrl).mockRejectedValueOnce(new Error('network error'));

    const user = userEvent.setup();
    render(<ConnectGmail />);
    await user.click(screen.getByText('Connect Gmail'));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});
