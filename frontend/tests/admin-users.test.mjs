import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const temp=await mkdtemp(path.join(process.cwd(),'tests/.admin-users-'));
try{
 const outfile=path.join(temp,'test.mjs');
 await build({stdin:{contents:`export * from './src/services/adminUserService';export {googleErrorMessage} from './src/services/googleAuthService';export {default as UserBillingDetails} from './src/components/admin/UserBillingDetails';export {AccountSummary} from './src/pages/admin/Users';export {default as api} from './src/services/api';`,resolveDir:process.cwd()},bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'},outfile,define:{'import.meta.env':'{}'}});
 const m=await import(pathToFileURL(outfile));const calls=[];
 m.api.defaults.adapter=async config=>{calls.push(config);return {data:{id:1,is_active:false,status_version:4},status:200,headers:{},config};};
 const signal=new AbortController().signal;
 await m.getAdminUsers({q:'name@example.com',role:'owner',status:'inactive',page:2},signal);await m.getAdminUser(1,signal);await m.setAdminUserStatus(1,false,3);
 assert.deepEqual(calls.map(c=>[c.method,c.url]),[['get','/admin/users'],['get','/admin/users/1'],['patch','/admin/users/1/status']]);
 assert.equal(calls[1].params.payment_page,1);assert.equal(calls[0].signal,signal);assert.equal(calls[0].params.status,'inactive');assert.deepEqual(JSON.parse(calls[2].data),{is_active:false,expected_version:3});
 for(const data of [{id:1,is_active:true,status_version:4},{id:2,is_active:false,status_version:4},{id:1,is_active:false},{id:1,is_active:false,status_version:2}]){
  m.api.defaults.adapter=async config=>({data,status:200,headers:{},config});
  await assert.rejects(m.setAdminUserStatus(1,false,3),error=>error.code==='STATUS_NOT_CONFIRMED' && /not confirmed/.test(m.adminUserError(error)));
 }
 m.api.defaults.adapter=async()=>{throw {response:{status:500}};};
 await assert.rejects(m.setAdminUserStatus(1,false,3));
 for(const role of ['user','owner'])for(const active of [true,false]){
  const html=renderToStaticMarkup(React.createElement(m.AccountSummary,{user:{name:'<script>bad</script>',email:'person@example.com',created_at:'2026-11-11T00:00:00',role,is_active:active,password_hash:'SECRET'}}));
  assert.match(html,active?/Active/:/Deactivated/);assert.match(html,role==='owner'?/Studio Owner/:/Normal User/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/SECRET|<script>/);
 }

 const billing=(props)=>renderToStaticMarkup(React.createElement(m.UserBillingDetails,{...props,onPaymentPage:()=>{}}));
 assert.match(billing({payments:{available:true,total:0,items:[]}}),/No payment history/);
 assert.match(billing({payments:{available:false}}),/Not available/);
 const recorded=billing({subscription:{plan:'Free Basic',allocated:10,used:0,remaining:10,note:'Recorded credits'},payments:{available:true,total:21,page:1,page_size:20,items:[{record_id:1,amount:'490.25',status:'<script>bad</script>',plan:'Free Basic'}]}});
 assert.match(recorded,/Used credits · current period<\/dt><dd>0<\/dd>/);
 assert.match(recorded,/490.25/);assert.match(recorded,/Next payments/);
 assert.match(recorded,/&lt;script&gt;/);assert.doesNotMatch(recorded,/<script>|LKR/);
 const normal=billing({subscription:{allowance_status:'used',note:'Monthly credits are not active.'},payments:{available:true,total:0,items:[]}});
 assert.match(normal,/One-time generation allowance/);assert.match(normal,/Not available/);
 assert.match(m.adminUserError({response:{status:409}}),/Refresh/);
 assert.match(m.googleErrorMessage({response:{status:401,data:{detail:'This account has been deactivated. Contact the administrator.'}}}),/deactivated/);
 assert.doesNotMatch(m.googleErrorMessage({response:{status:401,data:{detail:'untrusted backend text'}}}),/untrusted/);
 assert.match(m.adminUserError({}),/reach the server/);
 assert.match(m.adminUserError({response:{status:401}}),/sign in/);
 assert.match(m.adminUserError({response:{status:403}}),/permission/);
 assert.match(m.adminUserError({response:{status:503,data:{detail:{code:'ADMIN_USERS_SCHEMA_UNAVAILABLE'}}}}),/schema is missing or incompatible/);
 const unavailable=m.adminUserError({response:{status:503,data:{detail:'The database is temporarily unavailable.'}}});
 assert.match(unavailable,/temporarily unavailable/);assert.doesNotMatch(unavailable,/migration/);
 assert.match(m.adminUserError({response:{status:500}}),/unexpected server error/);
 const source=await readFile('src/pages/admin/Users.jsx','utf8');assert.match(source,/Confirm Deactivation/);assert.match(source,/showModal/);assert.match(source,/await setAdminUserStatus/);assert.match(source,/setConfirm\(user\)/);
 const routes=await readFile('src/routes/AppRoutes.jsx','utf8');assert.match(routes,/role === "admin" && <Route path="\/admin\/users"/);
}finally{await rm(temp,{recursive:true,force:true});}
