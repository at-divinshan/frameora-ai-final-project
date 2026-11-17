import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
const config = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url)));
test('existing assets are resolved before the SPA fallback', () => {
  assert.equal(config.routes[1].handle, 'filesystem');
  assert.equal(config.routes[2].dest, '/index.html');
  for (const route of ['/user/subscription', '/owner/projects/3', '/verify-email', '/auth/google/callback']) {
    assert.match(route, new RegExp(config.routes[2].src));
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
