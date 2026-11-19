import { describe, it, expect, vi } from 'vitest';
import { createNotifier } from '../../src/api/services/notifier.js';

describe('notifier', () => {
  it("envoie l'événement au service avec la clé d'API", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });
    const notifier = createNotifier({ url: 'http://notif.test', fetchImpl });

    await notifier.notify('ticket.created', { id: 1 });

    const [url, options] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://notif.test/v1/events');
    expect(options.headers.authorization).toMatch(/^Bearer ntf_/);
    expect(JSON.parse(options.body)).toMatchObject({ event: 'ticket.created', payload: { id: 1 } });
  });

  it("n'échoue jamais si le service est injoignable", async () => {
    const logger = { warn: vi.fn() };
    const fetchImpl = vi.fn().mockRejectedValue(new Error('getaddrinfo ENOTFOUND'));
    const notifier = createNotifier({ url: 'http://notif.test', fetchImpl, logger });

    await expect(notifier.notify('ticket.created', { id: 1 })).resolves.toBeUndefined();
    expect(logger.warn).toHaveBeenCalledOnce();
  });
});
