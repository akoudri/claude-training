import { describe, it, expect, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { createNotifier } from '../../src/api/services/notifier.js';

const config = { url: 'http://notif.test', apiKey: 'ntf_test_abcdefgh' };

describe('notifier', () => {
  it("envoie l'événement au service avec la clé d'API configurée", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });
    const notifier = createNotifier({ ...config, fetchImpl });

    await notifier.notify('ticket.created', { id: 1 });

    const [url, options] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://notif.test/v1/events');
    expect(options.headers.authorization).toBe('Bearer ntf_test_abcdefgh');
    expect(JSON.parse(options.body)).toMatchObject({ event: 'ticket.created', payload: { id: 1 } });
  });

  it("n'envoie rien et prévient une fois si la clé n'est pas configurée", async () => {
    const fetchImpl = vi.fn();
    const logger = { warn: vi.fn() };
    const notifier = createNotifier({ url: 'http://notif.test', apiKey: '', fetchImpl, logger });

    await notifier.notify('ticket.created', { id: 1 });
    await notifier.notify('ticket.created', { id: 2 });

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(logger.warn).toHaveBeenCalledOnce();
  });

  it('journalise un refus du service', async () => {
    const logger = { warn: vi.fn() };
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    const notifier = createNotifier({ ...config, fetchImpl, logger });

    await notifier.notify('ticket.created', { id: 1 });

    expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining('HTTP 401'));
  });

  it("n'échoue jamais si le service est injoignable", async () => {
    const logger = { warn: vi.fn() };
    const fetchImpl = vi.fn().mockRejectedValue(new Error('getaddrinfo ENOTFOUND'));
    const notifier = createNotifier({ ...config, fetchImpl, logger });

    await expect(notifier.notify('ticket.created', { id: 1 })).resolves.toBeUndefined();
    expect(logger.warn).toHaveBeenCalledOnce();
  });

  it('ne contient aucune clé en dur dans le code source', () => {
    const source = readFileSync(
      new URL('../../src/api/services/notifier.js', import.meta.url),
      'utf8',
    );
    expect(source).not.toMatch(/ntf_(live|test)_[a-z0-9]{8,}/);
  });
});
