import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const dir=await mkdtemp(path.join(process.cwd(),'tests/.payments-'));
try {
 const outfile=path.join(dir,'test.mjs');
 await build({stdin:{contents:`export * from './src/services/paymentService'; export * from './src/services/ownerPaymentService'; export {default as api,setAccessToken} from './src/services/api'; export {SubscriptionPlanCards} from './src/pages/user/Subscription'; export {PlanCards} from './src/pages/owner/Subscription'; export {default as UserBillingDetails} from './src/components/admin/UserBillingDetails';`,resolveDir:process.cwd()},bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'},outfile,define:{'import.meta.env':JSON.stringify({VITE_API_URL:'http://localhost:8000'})}});
 const m=await import(pathToFileURL(outfile));m.setAccessToken('mock-only');const requests=[];
 m.api.defaults.adapter=async config=>{requests.push(config);return {data:{mode:'test',checkout_url:'https://checkout.stripe.com/c/pay/test'},status:200,headers:{},config};};
 for(const [role,plans] of Object.entries({user:['starter','pro'],owner:['starter','growth','unlimited']}))for(const plan of plans){
  await m.startCheckout(role,plan,'stable-request-key');const request=requests.at(-1);
  assert.equal(request.url,`/${role}/payments/checkout`);assert.equal(request.headers.Authorization,'Bearer mock-only');
  assert.deepEqual(JSON.parse(request.data),{plan_code:plan,idempotency_key:'stable-request-key'});
 }
 for(const [role,plan] of [['admin','starter'],['user','growth'],['owner','pro']])await assert.rejects(m.startCheckout(role,plan,'key'));
 for(const [mode,url] of [['live','https://checkout.stripe.com/x'],['test','https://evil.test'],['test','https://user:pass@checkout.stripe.com/x'],['test','http://checkout.stripe.com/x']]){
  m.api.defaults.adapter=async config=>({data:{mode,checkout_url:url},status:200,headers:{},config});
  await assert.rejects(m.startCheckout('user','starter','key'));
 }
 let calls=0;m.api.defaults.adapter=async()=>{calls++;throw new Error('uncertain response');};
 await assert.rejects(m.startCheckout('owner','growth','same-key'));assert.equal(calls,1);
 const fetched=[];
 m.api.defaults.adapter=async config=>{fetched.push([config.method,config.url]);return {data:config.url.endsWith('readiness') ? {checkout_available:true,paid_activation_available:true} : {plan:'free',remaining_credits:0},status:200,headers:{},config};};
 const returned=await m.loadUserPaymentState();
 assert.deepEqual(fetched,[['get','/user/payments/readiness'],['get','/user/payments/subscription']]);
 assert.equal(returned.status.plan,'free');assert.equal(returned.status.remaining_credits,0);
 m.api.defaults.adapter=async config=>{if(config.url.endsWith('subscription'))throw {response:{status:503}};return {data:{checkout_available:false},status:200,headers:{},config};};
 assert.equal((await m.loadUserPaymentState()).status,null);
 m.api.defaults.adapter=async config=>{if(config.url.endsWith('subscription'))throw {response:{status:503}};return {data:{checkout_available:true},status:200,headers:{},config};};
 await assert.rejects(m.loadUserPaymentState());
 const cache=new Map();const storage={getItem:k=>cache.get(k),setItem:(k,v)=>cache.set(k,v),removeItem:k=>cache.delete(k)};
 const key=m.checkoutRequestKey('user',7,'starter',storage);
 assert.equal(m.checkoutRequestKey('user',7,'starter',storage),key);
 assert.notEqual(m.checkoutRequestKey('owner',7,'starter',storage),key);
 assert.notEqual(m.checkoutRequestKey('user',8,'starter',storage),key);
 m.clearCheckoutKey('user',7,'starter',storage);assert.notEqual(m.checkoutRequestKey('user',7,'starter',storage),key);
 assert.equal(m.checkoutExpired({response:{status:409,data:{detail:'Checkout expired. Start a new purchase.'}}}),true);
 assert.equal(m.checkoutExpired({response:{status:503}}),false);
 const originalWindow=globalThis.window;
 globalThis.window=Object.defineProperty({},'sessionStorage',{get(){throw new Error('Storage blocked');}});
 try { assert.match(m.checkoutRequestKey('user',7,'pro'),/^[a-z0-9-]{36}$/);m.clearCheckoutKey('user',7,'pro'); }
 finally { if(originalWindow === undefined)delete globalThis.window;else globalThis.window=originalWindow; }
 const ready={checkout_available:true,paid_activation_available:true};
 assert.equal(m.userCheckoutAllowed(ready,{plan:'free'}),true);
 for(const plan of ['starter','pro'])assert.equal(m.userCheckoutAllowed(ready,{plan}),false);
 assert.equal(m.ownerCheckoutAllowed(ready,{plan:'basic'}),true);
 for(const plan of ['trial','starter','growth','unlimited'])assert.equal(m.ownerCheckoutAllowed(ready,{plan}),false);
 assert.equal(m.userCheckoutAllowed({...ready,checkout_available:false},{plan:'free'}),false);
 const cards=renderToStaticMarkup(React.createElement(m.SubscriptionPlanCards,{readiness:ready,status:{plan:'free'},checkout(){}}));
 assert.equal((cards.match(/Continue to Stripe Test Checkout/g)||[]).length,2);assert.equal((cards.match(/disabled=""/g)||[]).length,1);
 const owner=renderToStaticMarkup(React.createElement(m.PlanCards,{plans:[{code:'starter',name:'Starter',price:1500,currency:'LKR',credits:100,max_projects:10,max_share_links:20}],status:{plan:'basic'},readiness:ready,activate(){}}));
 assert.match(owner,/Continue to Stripe Test Checkout/);assert.match(owner,/no automatic renewal/);
 const billing=renderToStaticMarkup(React.createElement(m.UserBillingDetails,{subscription:{plan:'Pro'},payments:{available:true,total:1,page:1,page_size:20,items:[{record_id:1,role:'user',transaction_id:'pi_recorded',currency:'LKR',status:'succeeded',provider:'stripe'}]},onPaymentPage(){}}));
 for(const text of ['pi_recorded','LKR','succeeded','stripe','user'])assert.ok(billing.includes(text));
 for(const role of ['user','owner']){
  const source=await readFile(`src/pages/${role}/Subscription.jsx`,'utf8');
  assert.match(source,/search/);assert.match(source,/Refresh subscription status/);assert.doesNotMatch(source,/set.*[Cc]redits\(/);
 }
} finally {await rm(dir,{recursive:true,force:true});}
