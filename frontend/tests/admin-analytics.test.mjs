import assert from 'node:assert/strict';
import {mkdtemp, rm, readFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import React from 'react';
import {renderToStaticMarkup as render} from 'react-dom/server';
const dir = await mkdtemp(path.join(process.cwd(), 'tests/.analytics-'));
try {
 const outfile=path.join(dir,'test.mjs');
 await build({stdin:{contents:`export * from './src/pages/admin/Analytics'; export * from './src/components/admin/AnalyticsCharts'; export * from './src/services/adminService'; export {default as api} from './src/services/api';`,resolveDir:process.cwd()},bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'},outfile,define:{'import.meta.env':'{}'}});
 const m=await import(pathToFileURL(outfile));
 m.api.defaults.adapter=async config=>{assert.equal(config.method,'get');assert.equal(config.url,'/admin/analytics');return {data:{users:0},status:200,headers:{},config};};
 assert.deepEqual(await m.getAdminAnalytics(),{users:0});
 const html=render(React.createElement(m.AnalyticsContent,{data:{users:0,owners:2,subscriptions:[{role:'owner',plan:'Starter',count:1},{role:'user',plan:'Starter',count:2}],payment_trend:[],registration_trend:null}}));
 for(const text of ['Test Mode','Not available','>0<']) assert.ok(html.includes(text));
 const chart=render(React.createElement(m.AnalyticsChart,{title:'Test Mode',rows:[{month:'2026-01',value:490}],currency:true}));assert.ok(!chart.includes('<meter'));assert.match(chart,/View chart data/);assert.match(chart,/LKR /);
 assert.deepEqual(m.continuousMonths([{month:'2025-12',value:'8'},{month:'2026-02',value:2}]),[{month:'2025-12',value:8},{month:'2026-01',value:0},{month:'2026-02',value:2}]);
 assert.equal(m.continuousMonths(null),null);assert.deepEqual(m.continuousMonths([]),[]);assert.equal(m.continuousMonths([{month:'2026-13',value:2}]),null);
 const limited=m.continuousMonths([{month:'2020-01',value:3},{month:'2026-02',value:4}]);assert.equal(limited.length,12);assert.equal(limited[0].month,'2025-03');assert.equal(limited[0].value,0);
 const donut=render(React.createElement(m.SubscriptionChart,{rows:[{role:'owner',plan:'Starter',count:1},{role:'user',plan:'Starter',count:2}]}));for(const text of ['Studio Owner','Normal User','33.3%','66.7%']) assert.ok(donut.includes(text));
 assert.match(render(React.createElement(m.SubscriptionChart,{rows:[]})),/No active subscriptions/);
 assert.match(render(React.createElement(m.AnalyticsChart,{title:'Missing',rows:null})),/Not available/);
 assert.match(render(React.createElement(m.AnalyticsChart,{title:'Empty',rows:[]})),/No recorded data/);
 const layout=await readFile('src/components/layout/AdminLayout.jsx','utf8');assert.ok(!layout.includes('Notifications'));assert.ok(layout.includes('/admin/analytics'));
 const sidebar=await readFile('src/components/layout/Sidebar.jsx','utf8');assert.ok(sidebar.includes('/user/notifications'));
 const css=await readFile('src/styles/admin-analytics.css','utf8');assert.match(css,/minmax\(0,1fr\)/);assert.match(css,/max-width: 480px/);
} finally {await rm(dir,{recursive:true,force:true});}
