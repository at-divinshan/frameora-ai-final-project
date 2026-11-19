import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const dir=await mkdtemp(path.join(process.cwd(),'tests/.subscription-layout-'));
try {
 const outfile=path.join(dir,'render.mjs');
 await build({stdin:{contents:`import React from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {SubscriptionPlanCards,StudioOwnerUpgradeCard,SubscriptionStatus} from './src/pages/user/Subscription';export function render(){const status={plan:'starter',remaining_credits:40,period_end:'2027-01-01T00:00:00',credits_per_batch:4};return renderToStaticMarkup(<div className="user-dashboard" style={{display:'block'}}><main style={{padding:12}}><section className="account-page user-subscription-page"><SubscriptionStatus status={status}/><div className="user-subscription-grid"><SubscriptionPlanCards status={status}/><StudioOwnerUpgradeCard status={status}/></div></section></main></div>)}`,resolveDir:process.cwd(),loader:'jsx'},bundle:true,outfile,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});
 const {render}=await import(pathToFileURL(outfile));
 const names=['variables','global','dashboard','account','ai','user-subscription'];
 const css=(await Promise.all(names.map(n=>readFile('src/styles/'+n+'.css','utf8')))).join('\n');
 assert.match(css,/\.user-subscription-page \.user-subscription-grid \{ grid-template-columns: minmax\(0, 1fr\)/);
 const cases=[];
 for(const theme of ['dark','light'])for(const width of [320,375,390,400,430,768,1440]){
  const src='<html data-theme="'+theme+'"><meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;; style-src &apos;unsafe-inline&apos;"><style>'+css+'</style>'+render()+'</html>';
  cases.push('<iframe data-theme="'+theme+'" style="width:'+width+'px;height:900px;border:0" srcdoc="'+src.replaceAll('&','&amp;').replaceAll('"','&quot;')+'"></iframe>');
 }
 const file=path.join(dir,'fixture.html');
 await writeFile(file,'<body>'+cases.join('')+`<script>onload=()=>{document.body.appendChild(Object.assign(document.createElement('pre'),{id:'results',textContent:JSON.stringify([...document.querySelectorAll('iframe')].map(f=>{const d=f.contentDocument;return {theme:f.dataset.theme,width:f.contentWindow.innerWidth,client:d.documentElement.clientWidth,scroll:d.documentElement.scrollWidth,cards:d.querySelectorAll('.user-subscription-card').length,columns:f.contentWindow.getComputedStyle(d.querySelector('.user-subscription-grid')).gridTemplateColumns.split(' ').length,buttons:[...d.querySelectorAll('button')].every(b=>{const r=b.getBoundingClientRect();return r.left>=0&&r.right<=d.documentElement.clientWidth+1})}}))}))}</script>`);
 if(process.env.FRAMEORA_LAYOUT_CHROME){
  const output=execFileSync(process.env.FRAMEORA_LAYOUT_CHROME,['--headless','--no-sandbox','--disable-gpu','--disable-background-networking','--host-resolver-rules=MAP * ~NOTFOUND','--user-data-dir='+path.join(dir,'chrome'),'--dump-dom',pathToFileURL(file).href],{encoding:'utf8',maxBuffer:32*1024*1024,timeout:90000,stdio:['ignore','pipe','ignore']});
  const match=output.match(/<pre id="results">([^<]+)<\/pre>/);assert.ok(match);
  const results=JSON.parse(match[1]);
  assert.equal(results.length,14);
  for(const r of results){
   assert.ok(r.scroll<=r.client,JSON.stringify(r));assert.equal(r.cards,4);assert.ok(r.buttons,JSON.stringify(r));
   assert.equal(r.columns,r.width<=600?1:r.width<=1250?2:4,JSON.stringify(r));
  }
  console.log('14 dark/light browser layouts passed, including full-width phone cards and contained buttons.');
 } else console.log('Chrome layout checks require FRAMEORA_LAYOUT_CHROME; static fixture checks passed.');
} finally {await rm(dir,{recursive:true,force:true});}
