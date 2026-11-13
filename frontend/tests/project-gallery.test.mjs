import assert from 'node:assert/strict';
import {mkdtemp, rm} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const temp = await mkdtemp(path.join(process.cwd(),'tests/.gallery-'));
try {
  const outfile=path.join(temp,'bundle.mjs');
  await build({stdin:{contents:`export {default as Folders, phaseLabel} from './src/components/ai/ProjectFolders'; export {publishProjectPhase} from './src/services/shareService'; export {getProjectGenerations} from './src/services/projectService'; export {default as api} from './src/services/api';`,resolveDir:process.cwd()},bundle:true,platform:'node',format:'esm',packages:'external',jsx:'automatic',outfile,define:{'import.meta.env':'{}'}});
  const {Folders,phaseLabel,publishProjectPhase,getProjectGenerations,api}=await import(pathToFileURL(outfile));
  const folders=[{key:'5',name:'Wedding',image_count:42,cover_id:7},{key:'unassigned',name:'Unassigned Images',image_count:4}];
  const markup=renderToStaticMarkup(React.createElement(Folders,{gallery:{folders,selected:null,open:()=>{}}}));
  assert.match(markup,/Wedding/);assert.match(markup,/42 images/);assert.match(markup,/Unassigned Images/);
  const detail=renderToStaticMarkup(React.createElement(Folders,{gallery:{folders,selected:folders[0],open:()=>{}}}));
  assert.match(detail,/Back to folders/);assert.doesNotMatch(detail,/Unassigned Images/);
  assert.equal(phaseLabel({id:3,phase_number:2}),'Phase 2');
  assert.equal(phaseLabel({id:3,status:'completed'}),'Legacy batch #3');
  let requests=[];
  api.defaults.adapter=async config=>{requests.push(config);return {data:config.method==='put'?{published:true}:config.params.before?[{id:1}]:Array.from({length:20},(_,i)=>({id:21-i})),status:200,headers:{},config};};
  const history=await getProjectGenerations(5);
  assert.equal(history.length,21);assert.equal(requests[1].params.before,2);
  await publishProjectPhase(5,9,2);
  assert.equal(requests[2].method,'put');assert.equal(requests[2].url,'/owner/projects/5/share-links/9/phases/2');
  console.log('Project folders, phase labels, history pagination and explicit publication checks passed.');
} finally {await rm(temp,{recursive:true,force:true});}
