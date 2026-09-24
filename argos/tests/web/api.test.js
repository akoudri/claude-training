import { describe, it, expect, vi, afterEach } from 'vitest';
import { api } from '../../src/web/api.js';

afterEach(() => vi.unstubAllGlobals());

function stubFetch(status, text) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(text, { status })));
}

describe('client API', () => {
  it("remonte le message d'erreur renvoyé par l'API", async () => {
    stubFetch(400, '{"error":"Le titre est obligatoire"}');
    await expect(api.createTicket({ title: '' })).rejects.toThrow('Le titre est obligatoire');
  });

  it("indique le code HTTP quand la réponse n'est pas du JSON", async () => {
    stubFetch(502, '<html>Bad Gateway</html>');
    await expect(api.getStats()).rejects.toThrow('HTTP 502');
  });
});
