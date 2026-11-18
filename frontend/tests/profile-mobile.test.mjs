import assert from 'node:assert/strict';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { build } from 'esbuild';
import { dismissWithEscape } from '../src/utils/keyboardDismiss.js';
const dir = await mkdtemp(path.join(process.cwd(), 'tests/.profile-mobile-'));
try {
  const outfile = path.join(dir, 'profile.mjs');
  await build({
    stdin: { contents: 'export {accountInformation} from "./src/components/common/AccountProfile.jsx";', resolveDir: process.cwd() },
    bundle:true, format:'esm', platform:'node', packages:'external', jsx:'automatic',
    loader:{'.css':'empty'}, define:{'import.meta.env':'{}'}, outfile,
  });
  const {accountInformation} = await import(pathToFileURL(outfile));
  for (const role of ['user','owner','admin']) {
    const profile = Object.freeze({role, email:'test@example.invalid', id:42, created_at:'2026-01-01', is_verified:true, has_password:true});
    const fields = accountInformation(profile);
    assert.deepEqual(fields.slice(0,3).map(([label])=>label), ['Email','Role','Verification']);
    assert.equal(fields.length, role === 'user' ? 3 : 6);
    assert.equal(fields[2][1], 'Verified');
  }
  assert.equal(accountInformation({role:'user',is_verified:false})[2][1], 'Not verified');
  const original = globalThis.window;
  try {
    for (const width of [320,375,390,430,768,1440]) {
      globalThis.window = {matchMedia:()=>({matches:width<=760})};
      let closed=0, focused=0;
      dismissWithEscape({key:'Escape',preventDefault(){},stopPropagation(){}},true,()=>closed++,{current:{focus:()=>focused++}},true);
      assert.equal(closed, Number(width<=760));
      assert.equal(focused, closed);
    }
  } finally { if(original===undefined)delete globalThis.window;else globalThis.window=original; }
  const css = await readFile('src/styles/dashboard.css','utf8');
  assert.ok(css.includes('.user-dashboard-navigation nav, .owner-navigation nav, .admin-navigation nav { grid-template-columns: minmax(0, 1fr); }'));
} finally { await rm(dir,{recursive:true,force:true}); }
