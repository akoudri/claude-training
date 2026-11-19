// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import TicketList from '../../src/web/components/TicketList.jsx';

const tickets = [
  { id: 1, title: 'Premier', status: 'open', priority: 'high' },
  { id: 2, title: 'Second', status: 'closed', priority: 'normal' },
];

afterEach(cleanup);

describe('<TicketList>', () => {
  it('affiche chaque ticket avec son statut et sa priorité', () => {
    render(<TicketList tickets={tickets} onSelect={() => {}} />);
    expect(screen.getByText('Premier')).toBeTruthy();
    expect(screen.getByText('Haute')).toBeTruthy();
    expect(screen.getByText('Clos')).toBeTruthy();
  });

  it('signale une liste vide', () => {
    render(<TicketList tickets={[]} onSelect={() => {}} />);
    expect(screen.getByText('Aucun ticket.')).toBeTruthy();
  });

  it('remonte le ticket cliqué', () => {
    const onSelect = vi.fn();
    render(<TicketList tickets={tickets} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Second'));
    expect(onSelect).toHaveBeenCalledWith(2);
  });
});
