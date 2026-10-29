// Isolated checks: no backend requests, database access, or real authentication.
// Run: node tests/account.test.mjs (from frontend).
import { build } from 'esbuild';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';
const directory = await mkdtemp(path.join(tmpdir(), 'frameora-account-'));
const source = `
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import assert from 'node:assert/strict';
import { validateProfile, validatePicture } from './src/utils/profile';
import api from './src/services/api';
import { updateProfile, updatePrivacy, uploadProfilePicture, getProfilePicture } from './src/services/userService';
import { AuthContext } from './src/context/AuthContext';
import { ThemeProvider } from './src/context/ThemeContext';
import AppRoutes from './src/routes/AppRoutes';
import { AccountSecurity } from './src/components/common/AccountSettings';
export async function validation() {
 assert.deepEqual(validateProfile({name:' Alice ',phone:'+94 (77) 123-4567'}),{});
 assert.ok(validateProfile({name:'A',phone:'abc'}).name);
 assert.ok(validateProfile({name:'Alice',phone:'123'}).phone);
 assert.ok(validateProfile({name:'A\\u0000B',phone:''}).name);
 assert.deepEqual(validateProfile({name:'Alice',phone:''}),{});
 assert.equal(validatePicture({type:'image/png',size:5*1024*1024}),'');
 assert.ok(validatePicture({type:'image/png',size:5*1024*1024+1}));
 assert.ok(validatePicture({type:'image/svg+xml',size:100}));
 assert.ok(validatePicture({type:'image/jpeg',size:0}));
}
export async function payloads() {
 let sent;
 api.defaults.adapter = async config => { sent=config; return {data:{},status:200,statusText:'OK',headers:{},config}; };
 await updateProfile({name:' Alice ',phone:' ',role:'admin',email:'ignored'});
 assert.deepEqual(JSON.parse(sent.data),{name:'Alice',phone:null});
 const privacy={profile_visibility:'public',photography_plans_default:'private',ai_images_default:'private',role:'admin'};
 await updatePrivacy(privacy,'user'); assert.deepEqual(Object.keys(JSON.parse(sent.data)).sort(),['ai_images_default','photography_plans_default','profile_visibility']);
 await updatePrivacy(privacy,'admin'); assert.equal(JSON.parse(sent.data).profile_visibility,undefined);
 const file=new Blob(['isolated fixture'],{type:'image/png'}); await uploadProfilePicture(file);
 assert.equal(sent.data,file); assert.equal(sent.headers.get('Content-Type'),'image/png'); assert.equal(sent.url,'/users/me/picture');
 api.defaults.adapter=async config=>({data:new Blob(['png'],{type:'image/png'}),status:200,headers:{},config});
 assert.equal((await getProfilePicture()).type,'image/png');
 api.defaults.adapter=async()=>{throw {response:{status:404}}}; assert.equal(await getProfilePicture(),null);
 api.defaults.adapter=async config=>({data:new Blob(['html'],{type:'text/html'}),status:200,headers:{},config});
 await assert.rejects(getProfilePicture());
}
export function security() {
 for (const role of ['user','owner','admin']) for (const has_password of [false,true]) for (const google_linked of [false,true]) {
  const html=renderToStaticMarkup(<MemoryRouter><AccountSecurity profile={{role,has_password,google_linked}} /></MemoryRouter>);
  if(role==='admin') assert.ok(!html.includes('Google'));
  if(has_password || role!=='admin') assert.ok(html.includes('disabled=""'));
  assert.equal(html.includes('href="/auth/google/link"'),role!=='admin' && has_password && !google_linked);
  assert.ok(!html.includes('type="password"'));
 }
}
export function route(role,target,page) {
 const user=role ? {id:'disposable-fixture',name:'Test Account',role} : null;
 const html=renderToStaticMarkup(<AuthContext.Provider value={{user,loading:false,refreshProfile:()=>{},refreshPicture:()=>{}}}><ThemeProvider><MemoryRouter initialEntries={['/'+target+'/'+page]}><AppRoutes /></MemoryRouter></ThemeProvider></AuthContext.Provider>);
 if(role!==target) { assert.equal(html,''); return; }
 assert.ok(html.includes('href="/'+role+'/profile"'));
 assert.ok(html.includes('href="/'+role+'/settings"'));
 assert.ok(html.includes(page==='profile' ? 'Loading profile' : 'Loading privacy settings'));
 if(role==='admin') assert.ok(!html.includes('Link Google account'));
}
`;
const result = await build({stdin:{contents:source,resolveDir:process.cwd(),loader:'jsx'},bundle:true,write:false,platform:'node',format:'esm',packages:'external',jsx:'automatic',loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});
// Keep external dependencies resolvable from the existing frontend installation.
const file = path.join(directory,'checks.mjs');
const { symlink } = await import('node:fs/promises');
await symlink(path.resolve('node_modules'),path.join(directory,'node_modules'));
await writeFile(file,result.outputFiles[0].text);
const checks=await import(pathToFileURL(file));
test('profile and file validation',checks.validation);
test('password controls disabled and Google controls excluded for Admin',checks.security);
test('API allowlists, raw uploads and safe image responses',checks.payloads);
for(const role of [null,'user','owner','admin']) for(const target of ['user','owner','admin']) for(const page of ['profile','settings']) {
 test((role||'anonymous')+' → '+target+'/'+page,()=>checks.route(role,target,page));
}
test.after(()=>rm(directory,{recursive:true,force:true}));
