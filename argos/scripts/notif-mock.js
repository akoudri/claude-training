// Faux service de notification, pour travailler sans le vrai service.
// Usage : npm run notif:mock   puis, dans .env : NOTIF_API_URL=http://localhost:4010
import { createServer } from 'node:http';

const PORT = Number(process.env.NOTIF_MOCK_PORT ?? 4010);

createServer((req, res) => {
  if (req.method !== 'POST' || req.url !== '/v1/events') {
    res.writeHead(404).end();
    return;
  }
  const auth = req.headers.authorization ?? '';
  if (!/^Bearer ntf_(live|test)_[a-z0-9]{8,}$/.test(auth)) {
    console.log(`✗ requête refusée : clé absente ou invalide`);
    res.writeHead(401, { 'content-type': 'application/json' }).end('{"error":"invalid api key"}');
    return;
  }
  let body = '';
  req.on('data', (chunk) => (body += chunk));
  req.on('end', () => {
    let message;
    try {
      message = JSON.parse(body || '{}');
    } catch {
      console.log('✗ requête refusée : corps JSON invalide');
      res.writeHead(400, { 'content-type': 'application/json' }).end('{"error":"invalid json"}');
      return;
    }
    const { event, payload } = message;
    const key = auth.slice('Bearer '.length);
    console.log(`✓ ${event} ${JSON.stringify(payload)} (clé ${key.slice(0, 9)}…)`);
    res.writeHead(202, { 'content-type': 'application/json' }).end('{"accepted":true}');
  });
}).listen(PORT, '127.0.0.1', () => console.log(`Service de notification simulé sur http://127.0.0.1:${PORT}`));
