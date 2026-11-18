import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {build} from 'esbuild';
const temp=await mkdtemp(path.join(process.cwd(),'tests/.oauth-proxy-'));
const originalWindow=globalThis.window;
try {
  globalThis.window={location:{origin:'https://frontend.example'}};
  for (const production of [true,false]) {
    const outfile=path.join(temp,`${production}.mjs`);
    await build({entryPoints:['src/services/api.js'],bundle:true,platform:'node',format:'esm',packages:'external',outfile,
      define:{'import.meta.env':JSON.stringify({PROD:production,VITE_API_URL:'https://backend.example'})}});
    const {default:api,setAccessToken,setUnauthorizedHandler}=await import(pathToFileURL(outfile));
    setAccessToken('synthetic-session');let loggedOut=0;setUnauthorizedHandler(()=>loggedOut++);
    const requests=[];api.defaults.adapter=async config=>{requests.push(config);return {data:{},status:200,headers:{},config};};
    for (const endpoint of ['start','complete','register','link/start','link/complete','password-setup/start','password-setup/complete']) {
      await api.post(`/auth/google/${endpoint}`,{});
      const request=requests.at(-1);
      assert.equal(request.baseURL,production?'https://frontend.example/oauth-api':'https://backend.example');
      assert.equal(request.headers.Authorization,'Bearer synthetic-session');
      if (production) assert.equal(request.withCredentials,true);
    }
    await api.get('/user/payments/readiness');
    assert.equal(requests.at(-1).baseURL,'https://backend.example');
    api.defaults.adapter=async config=>{throw {config,response:{status:401}};};
    await assert.rejects(api.post('/auth/google/link/start',{}));
    assert.equal(loggedOut,0);
  }
  console.log('OAuth proxy routing, local compatibility, JWT forwarding and linking error checks passed.');
} finally {globalThis.window=originalWindow;await rm(temp,{recursive:true,force:true});}
