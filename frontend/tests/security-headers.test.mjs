import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import config from '../vite.config.js';

test('development and preview deny framing without restricting OAuth, images or HMR',()=>{
  for(const headers of [config.server.headers,config.preview.headers]){
    assert.equal(headers['X-Frame-Options'],'DENY');
    assert.match(headers['Content-Security-Policy'],/frame-ancestors 'none'/);
    assert.doesNotMatch(headers['Content-Security-Policy'],/script-src|connect-src|img-src|default-src/);
    assert.equal(headers['Referrer-Policy'],'no-referrer');
  }
});
test('built HTML source includes portable baseline CSP and referrer policy',async()=>{
  const html=await readFile('index.html','utf8');
  assert.match(html,/object-src 'none'; base-uri 'self'/);
  assert.match(html,/name="referrer" content="no-referrer"/);
  assert.doesNotMatch(html,/frame-ancestors/); // This directive requires an HTTP header.
});
