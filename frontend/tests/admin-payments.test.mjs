import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import React from 'react';
import {renderToStaticMarkup as render} from 'react-dom/server';
const dir=await mkdtemp(path.join(process.cwd(),'tests/.admin-payments-'));
try {
 const outfile=path.join(dir,'test.mjs');
 await build({stdin:{contents:`export * from './src/pages/admin/Payments';export * from './src/services/adminPaymentService';export {default as api,setAccessToken} from './src/services/api';`,resolveDir:process.cwd()},bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'},outfile,define:{'import.meta.env':'{}'}});
 const m=await import(pathToFileURL(outfile));m.setAccessToken('fixture');const requests=[];
 m.api.defaults.adapter=async config=>{requests.push(config);return {data:{items:[]},status:200,headers:{},config};};
 const filters={role:'owner',plan:'starter',status:'succeeded',date_from:'2026-01-01',page:2};
 await m.getAdminPayments(filters);assert.deepEqual(requests[0].params,filters);assert.equal(requests[0].headers.Authorization,'Bearer fixture');
 await m.getAdminPayment('payment',1);assert.equal(requests[1].url,'/admin/payments/payment/1');assert.ok(requests.every(r=>r.method==='get'));
 assert.match(render(React.createElement(m.PaymentRows,{items:[]})),/No payment records found/);
 const items=['user','owner'].map((role,i)=>({kind:'payment',id:i,role,name:'Fixture',email:'fixture@example.test',plan:'starter',amount:'490',currency:'lkr',status:'succeeded',transaction_id:'pi_fixture'}));
 const html=render(React.createElement(m.PaymentRows,{items,onSelect:()=>{}}));for(const label of ['Normal User','Studio Owner','pi_fixture','View Details'])assert.ok(html.includes(label));
 assert.equal(m.formatPaymentAmount('1500.0000','lkr'),'LKR 1,500.00');
 assert.equal(m.formatPaymentAmount('490','LKR'),'LKR 490.00');
 assert.equal(m.formatPaymentAmount(0,'LKR'),'LKR 0.00');
 for (const n of [null,undefined,'','bad',Infinity]) assert.equal(m.formatPaymentAmount(n,'LKR'),'Not available');
 assert.equal(m.formatPaymentAmount('490',null),'490.00 (currency unavailable)');
 for (const status of ['succeeded','pending','expired','failed','refunded','disputed','partially_refunded']) {
   const badge=render(React.createElement(m.PaymentStatus,{status}));
   assert.ok(badge.includes(`payment-status--${status}`));
 }
 assert.match(render(React.createElement(m.PaymentStatus,{status:'pending',checkout:true})),/Pending checkout/);
 assert.match(html,/payment-table-scroll/);assert.match(html,/tabindex="0"/);assert.match(html,/scope="col"/);assert.match(html,/LKR 490.00/);
 const summary=render(React.createElement(m.PaymentSummary,{summary:{successful:2,revenue:'1990.0000',pending:0,failed_refunded:0}}));assert.match(summary,/LKR 1,990.00/);
 const detail=render(React.createElement(m.PaymentDetail,{record:{...items[0],events:[],allocation:null,subscription:null}}));assert.match(detail,/Not available/);assert.match(detail,/No recorded events/);
} finally {await rm(dir,{recursive:true,force:true});}
