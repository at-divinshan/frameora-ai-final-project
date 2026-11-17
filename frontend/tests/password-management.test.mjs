import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { mkdtemp,rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
test('password setup uses authenticated Google endpoint and consent without storing credentials',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'password-ui-'));
 try {
  await build({stdin:{contents:`import api from './src/services/api'; import {startGoogle,readGoogleFlow} from './src/services/googleAuthService'; export {api,startGoogle,readGoogleFlow};`,resolveDir:process.cwd()},banner:{js:"import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);"},bundle:true,platform:'node',format:'esm',outfile:join(dir,'test.mjs'),define:{'import.meta.env.VITE_API_URL':'"http://localhost:8000"'}});
  const {api,startGoogle,readGoogleFlow}=await import(pathToFileURL(join(dir,'test.mjs')));
  const storage=new Map();globalThis.sessionStorage={getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
  let redirected;globalThis.window={location:{assign:url=>redirected=url}};
  api.post=async(path,body,options)=>{assert.equal(path,'/auth/google/password-setup/start');assert.deepEqual(body,{consent:true});assert.equal(options.withCredentials,true);return {data:{authorization_url:'https://accounts.google.com/o/oauth2/v2/auth?state=fixture'}};};
  await startGoogle({setup:true,userId:'1'});
  assert.equal(readGoogleFlow().mode,'password-setup');assert.equal(readGoogleFlow().userId,'1');assert.match(redirected,/accounts.google.com/);
  assert.doesNotMatch(JSON.stringify([...storage.values()]),/password_hash|access_token|current_password/);
 } finally {delete globalThis.window;delete globalThis.sessionStorage;await rm(dir,{recursive:true,force:true});}
});
