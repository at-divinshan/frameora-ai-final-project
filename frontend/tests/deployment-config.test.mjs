import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
const config = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url)));
test('existing assets are resolved before the SPA fallback', () => {
  assert.equal(config.routes[2].handle, 'filesystem');
  assert.equal(config.routes[3].dest, '/index.html');
  for (const route of ['/user/subscription', '/owner/projects/3', '/verify-email', '/auth/google/callback']) {
    assert.match(route, new RegExp(config.routes[3].src));
  }
});
test('production headers preserve API/image connections and deny framing', () => {
  const headers = config.routes[0].headers;
  assert.equal(config.routes[0].continue, true);
  assert.equal(headers['X-Frame-Options'], 'DENY');
  assert.match(headers['Content-Security-Policy'], /frame-ancestors 'none'/);
  assert.doesNotMatch(headers['Content-Security-Policy'], /connect-src|img-src/);
  assert.equal(headers['Referrer-Policy'], 'no-referrer');
});
test('OAuth proxy has a fixed destination and keeps the SPA completion separate', () => {
  const route = config.routes[1];
  const regex = new RegExp(`^${route.src}$`);
  for (const path of ['start','callback','complete','register','link/start','link/complete','password-setup/start','password-setup/complete'])
    assert.match(`/oauth-api/auth/google/${path}`, regex);
  for (const path of ['/auth/google/callback','/payments/stripe/webhook','/oauth-api/auth/google/unknown'])
    assert.doesNotMatch(path, regex);
  assert.equal(route.dest, 'https://frameora-ai-final-project-production.up.railway.app/auth/google/$1');
  assert.equal(route.headers['Cache-Control'], 'no-store');
});
