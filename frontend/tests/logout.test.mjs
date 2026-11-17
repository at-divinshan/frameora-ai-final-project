import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
test('logout calls authenticated API before cleanup and cleans up on failure',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'logout-test-'));
 try {
  await build({stdin:{contents:`export {logoutAndClear,clearStoredSession} from './src/services/authService';export {default as api,setAccessToken} from './src/services/api';`,resolveDir:process.cwd()},bundle:true,platform:'node',format:'esm',banner:{js:"import {createRequire} from 'node:module'; const require=createRequire(import.meta.url);"},outfile:join(dir,'test.mjs'),define:{'import.meta.env':'{}'}});
  const m=await import(pathToFileURL(join(dir,'test.mjs')));
  for(const fail of [false,true]) {
   const events=[];const local=new Map([['frameora.auth','fixture']]);const session=new Map([['frameora.auth','fixture']]);
   globalThis.window={localStorage:{removeItem:k=>local.delete(k)},sessionStorage:{removeItem:k=>session.delete(k)}};
   m.setAccessToken('fixture-token');
   m.api.defaults.adapter=async config=>{
    events.push('request');assert.equal(config.url,'/auth/logout');assert.equal(config.headers.Authorization,'Bearer fixture-token');assert.equal(config.timeout,5000);
    assert.equal(local.size,1);assert.equal(session.size,1);
    if(fail)throw new Error('offline');
    return {data:null,status:204,headers:{},config};
   };
   const confirmed=await m.logoutAndClear(()=>{events.push('cleanup');m.clearStoredSession();m.setAccessToken(null);});
   assert.equal(confirmed,!fail);assert.deepEqual(events,['request','cleanup']);assert.equal(local.size,0);assert.equal(session.size,0);
  }
  const context=await readFile('src/context/AuthContext.jsx','utf8');
  assert.match(context,/setUnauthorizedHandler\(\(\) => clearAuth/);
  assert.match(context,/revision.current === started/);
  assert.match(context,/if \(logoutPending.current\) return logoutPending.current/);
 } finally {delete globalThis.window;await rm(dir,{recursive:true,force:true});}
});
