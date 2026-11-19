import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const dir=await mkdtemp(path.join(process.cwd(),'tests/.owner-subscription-layout-'));
try {
 const outfile=path.join(dir,'render.mjs');
 await build({stdin:{contents:`import React from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {PlanCards,OwnerSubscriptionStatus} from './src/pages/owner/Subscription';
const plans=[['basic','Free Basic',0,10,2,3],['trial','Free Trial',0,100,null,null],['starter','Starter',1500,100,10,20],['growth','Growth',2500,250,30,60],['unlimited','Unlimited',3500,500,null,null]].map(([code,name,price,credits,max_projects,max_share_links])=>({code,name,price,credits,max_projects,max_share_links,currency:'LKR',credit_period:code==='trial'?'trial_total':'monthly',trial_days:code==='trial'?14:null,activation_available:['basic','trial'].includes(code)}));
export function cards(plan='trial',available=false){return renderToStaticMarkup(<PlanCards plans={plans} status={{plan,trial_available:available}} readiness={{checkout_available:true,paid_activation_available:true}} busy="" activate={()=>{}}/>);}
export function summary(){return renderToStaticMarkup(<OwnerSubscriptionStatus plans={plans} status={{plan:'starter',remaining_credits:0,period_end:'2027-01-01T00:00:00'}}/>);}
export function render(){return renderToStaticMarkup(<div className="owner-dashboard" style={{display:'block'}}><main className="account-page" style={{padding:12}}><section className="owner-subscription-page"><OwnerSubscriptionStatus plans={plans} status={{plan:'trial',remaining_credits:92,period_end:'2027-01-01T00:00:00'}}/><PlanCards plans={plans} status={{plan:'trial',trial_available:false}} readiness={{checkout_available:true,paid_activation_available:true}} busy="" activate={()=>{}}/></section></main></div>)}`,resolveDir:process.cwd(),loader:'jsx'},bundle:true,outfile,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});
 const {render,cards,summary}=await import(pathToFileURL(outfile));
 const active=cards();
 assert.equal((active.match(/disabled=""/g)||[]).length,5);
 assert.ok(active.includes('Your lifetime trial has already been used.'));
 assert.equal((active.match(/is-current/g)||[]).length,1);
 for(const price of ['1,500','2,500','3,500']) assert.ok(active.includes(price));
 assert.ok(cards('basic',true).includes('Start Free Trial'));
 assert.ok(cards('starter').includes('Current plan'));
 assert.ok(summary().includes('>0</dd>'));
 assert.ok(summary().includes('2027'));
 const names=['variables','global','dashboard','account','owner-subscription'];
 const css=(await Promise.all(names.map(n=>readFile('src/styles/'+n+'.css','utf8')))).join('\n');
 assert.ok(css.includes('grid-template-columns: minmax(0,1fr)'));
 const cases=[];
 for(const theme of ['dark','light'])for(const width of [320,375,390,400,430,768,1440]){
  const src='<html data-theme="'+theme+'"><meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;; style-src &apos;unsafe-inline&apos;"><style>'+css+'</style>'+render()+'</html>';
  cases.push('<iframe data-theme="'+theme+'" style="width:'+width+'px;height:900px;border:0" srcdoc="'+src.replaceAll('&','&amp;').replaceAll('"','&quot;')+'"></iframe>');
 }
 const file=path.join(dir,'fixture.html');
 await writeFile(file,'<body>'+cases.join('')+`<script>onload=()=>{document.body.appendChild(Object.assign(document.createElement('pre'),{id:'results',textContent:JSON.stringify([...document.querySelectorAll('iframe')].map(f=>{const d=f.contentDocument;return {theme:f.dataset.theme,width:f.contentWindow.innerWidth,client:d.documentElement.clientWidth,scroll:d.documentElement.scrollWidth,cards:d.querySelectorAll('.studio-plan').length,columns:f.contentWindow.getComputedStyle(d.querySelector('.studio-plan-grid')).gridTemplateColumns.split(' ').length,buttons:[...d.querySelectorAll('button')].every(b=>{const r=b.getBoundingClientRect();return r.left>=0&&r.right<=d.documentElement.clientWidth+1})}}))}))}</script>`);
 if(process.env.FRAMEORA_LAYOUT_CHROME){
  const output=execFileSync(process.env.FRAMEORA_LAYOUT_CHROME,['--headless','--no-sandbox','--disable-gpu','--disable-background-networking','--host-resolver-rules=MAP * ~NOTFOUND','--user-data-dir='+path.join(dir,'chrome'),'--dump-dom',pathToFileURL(file).href],{encoding:'utf8',maxBuffer:32*1024*1024,timeout:90000,stdio:['ignore','pipe','ignore']});
  const match=output.match(/<pre id="results">([^<]+)<\/pre>/);assert.ok(match);
  const results=JSON.parse(match[1]);
  assert.equal(results.length,14);
  for(const r of results){
   assert.ok(r.scroll<=r.client,JSON.stringify(r));assert.equal(r.cards,5);assert.ok(r.buttons,JSON.stringify(r));
   assert.equal(r.columns,r.width<=600?1:r.width<=1100?2:6,JSON.stringify(r));
  }
  console.log('14 Owner dark/light browser layouts passed; 5 cards and contained buttons.');
 } else console.log('Chrome layout checks require FRAMEORA_LAYOUT_CHROME; static fixture checks passed.');
} finally {await rm(dir,{recursive:true,force:true});}
