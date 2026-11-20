import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const dir=await mkdtemp(path.join(process.cwd(),'tests/.analytics-layout-'));
try {
 const {outputFiles}=await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import Charts from './src/components/admin/AnalyticsCharts';
const trend=[{month:'2026-01',value:4},{month:'2026-03',value:8}];createRoot(document.getElementById('root')).render(<div className="admin-analytics"><Charts data={{subscriptions:[{role:'owner',plan:'Starter',count:2},{role:'user',plan:'Pro',count:1}],payment_trend:trend,registration_trend:trend,image_trend:trend}}/></div>);`,resolveDir:process.cwd(),loader:'jsx'},bundle:true,format:'iife',platform:'browser',jsx:'automatic',write:false,define:{'process.env.NODE_ENV':'"production"'}});
 const css=(await Promise.all(['variables','global','admin-analytics'].map(n=>readFile('src/styles/'+n+'.css','utf8')))).join('\n');
 const frames=[];
 for(const theme of ['dark','light'])for(const width of [320,375,390,400,430,768,1440]){
  const doc=`<!doctype html><html data-theme="${theme}"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"><style>${css} body{margin:0;padding:12px;box-sizing:border-box}</style><div id="root"></div><script>${outputFiles[0].text.replaceAll('</script','<\\/script')}</script></html>`;
  frames.push(`<iframe data-theme="${theme}" style="width:${width}px;height:1800px;border:0" srcdoc="${doc.replaceAll('&','&amp;').replaceAll('"','&quot;')}"></iframe>`);
 }
 const file=path.join(dir,'fixture.html');
 await writeFile(file,'<!doctype html><body>'+frames.join('')+`<script>onload=()=>setTimeout(()=>{document.body.appendChild(Object.assign(document.createElement('pre'),{id:'results',textContent:JSON.stringify([...document.querySelectorAll('iframe')].map(f=>{const d=f.contentDocument;return {theme:f.dataset.theme,width:f.contentWindow.innerWidth,scroll:d.documentElement.scrollWidth,client:d.documentElement.clientWidth,charts:d.querySelectorAll('svg.recharts-surface').length,line:d.querySelectorAll('.recharts-line').length,bars:d.querySelectorAll('.recharts-bar').length,pie:d.querySelectorAll('.recharts-pie').length,contained:[...d.querySelectorAll('.analytics-plot')].every(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&r.left>=0&&r.right<=d.documentElement.clientWidth+1}),text:f.contentWindow.getComputedStyle(d.querySelector('.admin-analytics')).color}}))}))},2500)</script>`);
 if(process.env.FRAMEORA_LAYOUT_CHROME){
  const output=execFileSync(process.env.FRAMEORA_LAYOUT_CHROME,['--headless','--no-sandbox','--disable-gpu','--disable-background-networking','--host-resolver-rules=MAP * ~NOTFOUND','--user-data-dir='+path.join(dir,'chrome'),'--virtual-time-budget=10000','--dump-dom',pathToFileURL(file).href],{encoding:'utf8',maxBuffer:64*1024*1024,timeout:90000,stdio:['ignore','pipe','ignore']});
  const match=output.match(/<pre id="results">([^<]+)<\/pre>/);assert.ok(match,'Browser fixture did not complete');
  const results=JSON.parse(match[1]);assert.equal(results.length,14);
  for(const r of results){assert.ok(r.scroll<=r.client,JSON.stringify(r));assert.ok(r.contained,JSON.stringify(r));assert.equal(r.charts,4,JSON.stringify(r));assert.equal(r.line,1);assert.equal(r.bars,2);assert.equal(r.pie,1);}
  assert.notEqual(results[0].text,results[7].text);
  console.log('14 offline browser fixtures passed: dark/light, 320–1440px, line/bar/donut rendering and no horizontal overflow.');
 } else console.log('Browser checks not run: set FRAMEORA_LAYOUT_CHROME. Chart bundle compiled successfully.');
} finally {await rm(dir,{recursive:true,force:true});}
