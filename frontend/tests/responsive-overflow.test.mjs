import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';import {readFile,writeFile} from 'node:fs/promises';
const dir=await mkdtemp(path.join(process.cwd(),'tests/.overflow-'));
try {
await build({stdin:{contents:`import React from 'react';import {renderToStaticMarkup} from 'react-dom/server';import {MemoryRouter} from 'react-router-dom';import {AuthContext} from './src/context/AuthContext';import {ThemeProvider} from './src/context/ThemeContext';import AccountProfile from './src/components/common/AccountProfile';export function render(role){return renderToStaticMarkup(<AuthContext.Provider value={{user:{id:1,role,name:'A long normal account name'},refreshProfile(){}}}><ThemeProvider><MemoryRouter><AccountProfile/></MemoryRouter></ThemeProvider></AuthContext.Provider>)}`,resolveDir:process.cwd(),loader:'jsx'},outfile:path.join(dir,'render.mjs'),bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'},define:{'import.meta.env':'{}'},plugins:[{name:'fixture',setup(b){b.onLoad({filter:/AccountProfile.jsx$/},async({path})=>({contents:(await readFile(path,'utf8')).replace('useState(null)','useState({id:1,role:user.role,name:"Test",email:"test@example.invalid",has_password:true})'),loader:'jsx'}))}}]});
const {render}=await import(pathToFileURL(path.join(dir,'render.mjs')));
const css=(await Promise.all(['variables','global','auth','responsive','dashboard','account','notifications'].map(f=>readFile('src/styles/'+f+'.css','utf8')))).join('\n');
assert.ok(css.includes('min-width: min(320px, 100%)'));
const cases=[];
for(const role of ['user','owner','admin'])for(const width of [320,375,390,400,430,768,1440]){
const src=`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';"><style>`+css+"</style>"+render(role);
cases.push('<iframe data-role="'+role+'" style="width:'+width+'px;height:671px;border:0" srcdoc="'+src.replaceAll('&','&amp;').replaceAll('"','&quot;')+'"></iframe>');
}
await writeFile(path.join(dir,'fixture.html'),'<body>'+cases.join('')+`<script>onload=()=>{const results=[...document.querySelectorAll('iframe')].map(f=>{const d=f.contentDocument,w=f.contentWindow.innerWidth;return {role:f.dataset.role,w,client:d.documentElement.clientWidth,scroll:d.documentElement.scrollWidth,wide:[...d.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>w+1).map(e=>[e.className,Math.round(e.getBoundingClientRect().width)])}});document.body.appendChild(Object.assign(document.createElement('pre'),{id:'results',textContent:JSON.stringify(results)}))}</script>`);

if (process.env.FRAMEORA_LAYOUT_CHROME) {
 const output=execFileSync(process.env.FRAMEORA_LAYOUT_CHROME,[
  '--headless','--no-sandbox','--disable-gpu','--disable-background-networking',
  '--host-resolver-rules=MAP * ~NOTFOUND',
  '--user-data-dir='+path.join(dir,'chrome'),'--dump-dom',pathToFileURL(path.join(dir,'fixture.html')).href
 ],{encoding:'utf8',maxBuffer:32*1024*1024,stdio:['ignore','pipe','ignore']});
 const match=output.match(/<pre id="results">([^<]+)<\/pre>/);
 assert.ok(match,'Chrome must return layout measurements');
 const results=JSON.parse(match[1].replaceAll('&quot;','"').replaceAll('&amp;','&'));
 assert.equal(results.length,21);
 for(const r of results) assert.ok(r.scroll<=r.client,JSON.stringify(r));
 console.log('PASS: 21 browser-measured Profile layouts (3 roles × 7 widths), including 400 × 671.');
} else console.log('Browser measurements skipped: set FRAMEORA_LAYOUT_CHROME to a local Chrome executable.');
} finally { await rm(dir,{recursive:true,force:true}); }
