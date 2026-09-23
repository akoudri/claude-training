// Filtre de la liste des tickets.
//   open   : tickets non clos (ouverts ou en cours)
//   closed : tickets clos
//   all    : tous les tickets
export function filterByStatus(tickets, status = 'all') {
  switch (status) {
    case 'open':
      return tickets.filter((t) => t.status !== 'closed');
    case 'closed':
      return tickets.filter((t) => t.status === 'closed');
    default:
      return tickets;
  }
}
