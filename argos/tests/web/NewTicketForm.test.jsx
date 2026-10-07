// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import NewTicketForm from '../../src/web/components/NewTicketForm.jsx';
import { api } from '../../src/web/api.js';

vi.mock('../../src/web/api.js', () => ({ api: { createTicket: vi.fn() } }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('<NewTicketForm>', () => {
  it('associe un libellé à chaque champ', () => {
    render(<NewTicketForm onCreated={() => {}} />);
    expect(screen.getByLabelText('Titre')).toBeTruthy();
    expect(screen.getByLabelText('Description')).toBeTruthy();
    expect(screen.getByLabelText('Priorité')).toBeTruthy();
  });

  it("n'envoie qu'une création en cas de double clic", async () => {
    let resolve;
    api.createTicket.mockReturnValue(new Promise((r) => (resolve = r)));
    const onCreated = vi.fn();
    render(<NewTicketForm onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText('Titre'), { target: { value: 'Panne' } });
    const button = screen.getByRole('button', { name: 'Créer' });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(api.createTicket).toHaveBeenCalledOnce();
    resolve({ id: 1 });
    await vi.waitFor(() => expect(onCreated).toHaveBeenCalledOnce());
  });
});
