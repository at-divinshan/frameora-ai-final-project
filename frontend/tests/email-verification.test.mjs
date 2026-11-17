import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
test('verification page never exposes token in markup or offers actions before readiness', async () => {
 const dir=await mkdtemp(join(tmpdir(),'verification-ui-'));
 try {
  await build({stdin:{contents:`import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {MemoryRouter} from 'react-router-dom'; import EmailVerification from './src/pages/auth/EmailVerification'; import {ThemeProvider} from './src/context/ThemeContext'; export function render(){return renderToStaticMarkup(<ThemeProvider><MemoryRouter><EmailVerification/></MemoryRouter></ThemeProvider>);}`,loader:'jsx',resolveDir:process.cwd()},jsx:'automatic',bundle:true,platform:'node',format:'esm',outfile:join(dir,'test.mjs'),banner:{js:"import {createRequire} from 'node:module'; const require=createRequire(import.meta.url);"},define:{'import.meta.env.VITE_API_URL':'"http://localhost:8000"'}});
  globalThis.window={location:{hash:'#token=private-verification-fixture'}};
  const {render}=await import(pathToFileURL(join(dir,'test.mjs')));
  const html=render();
  assert.match(html,/Checking verification availability/);
  assert.doesNotMatch(html,/private-verification-fixture|Resend verification email/);
  assert.match(html,/Back to login/);
 } finally { delete globalThis.window;await rm(dir,{recursive:true,force:true}); }
});

test('SMTP availability gates resend separately from token verification', async () => {
 const {readFile}=await import('node:fs/promises');
 const source=await readFile('src/pages/auth/EmailVerification.jsx','utf8');
 assert.match(source,/setDeliveryAvailable\(data\.delivery_available === true\)/);
 assert.match(source,/resend && \(cooldown \|\| !deliveryAvailable\)/);
 assert.match(source,/\{token && <form onSubmit=\{event => submit\(event, false\)\}/);
 assert.match(source,/Existing links can still be verified/);
});
