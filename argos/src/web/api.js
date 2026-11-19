async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'content-type': 'application/json' },
    ...options,
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
  return body;
}

export const api = {
  listTickets: (status) => request(`/tickets?status=${status}`),
  getStats: () => request('/stats'),
  createTicket: (ticket) => request('/tickets', { method: 'POST', body: JSON.stringify(ticket) }),
  updateTicket: (id, changes) =>
    request(`/tickets/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
};
