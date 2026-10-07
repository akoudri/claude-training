// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import App from '../../src/web/App.jsx';
import { api } from '../../src/web/api.js';

vi.mock('../../src/web/api.js', () => ({
  api: { listTickets: vi.fn(), getStats: vi.fn(), createTicket: vi.fn(), updateTicket: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

const ticket = {
  id: 1,
  title: 'Panne',
  description: '',
  status: 'open',
  priority: 'normal',
  assignee: null,
  created_at: '2026-09-24 10:00:00',
};

describe('<App>', () => {
  it('garde le détail affiché quand le ticket est clos sous le filtre « Ouverts »', async () => {
    api.getStats.mockResolvedValue({ total: 1, open: 1, in_progress: 0, closed: 0 });
    api.listTickets.mockResolvedValueOnce([ticket]).mockResolvedValue([]);
    api.updateTicket.mockResolvedValue({ ...ticket, status: 'closed' });
    render(<App />);

    fireEvent.click(await screen.findByText('Panne'));
    fireEvent.change(screen.getByLabelText(/Statut/), { target: { value: 'closed' } });

    expect(await screen.findByText('Aucun ticket.')).toBeTruthy();
    expect(screen.getByRole('heading', { name: /#1 — Panne/ })).toBeTruthy();
  });
});
