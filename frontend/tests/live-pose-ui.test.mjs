// Render the actual initial page with isolated auth and no browser/provider activity.
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
const temporary=await mkdtemp(path.join(process.cwd(),'tests/.live-pose-'));
try {
  const outfile=path.join(temporary,'page.mjs');
  await build({stdin:{contents:`
    import React from 'react';
    import {renderToStaticMarkup} from 'react-dom/server';
    import {MemoryRouter} from 'react-router-dom';
    import {AuthContext} from './src/context/AuthContext';
    import {ThemeProvider} from './src/context/ThemeContext';
    import LivePoseGuide from './src/pages/shared/LivePoseGuide';
    import api from './src/services/api';
    export let calls=0;
    api.defaults.adapter=()=>{calls++;throw new Error('No requests expected during initial render');};
    export function render(role){return renderToStaticMarkup(<MemoryRouter><ThemeProvider><AuthContext.Provider value={{user:{id:1,name:'Isolated test',role}}}><LivePoseGuide/></AuthContext.Provider></ThemeProvider></MemoryRouter>);}
  `,resolveDir:process.cwd(),loader:'jsx'},bundle:true,format:'esm',platform:'node',packages:'external',outfile,jsx:'automatic',loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});
  const module=await import(pathToFileURL(outfile));
  for(const role of ['user','owner']) {
    const html=module.render(role);
    assert.match(html,/Something Exciting is Coming!/);
    assert.match(html,/Coming Soon/);
    assert.match(html,/The perfect pose is on its way!/);
    assert.doesNotMatch(html,/Open Camera|Analyze Scene|Capture photo|<video|<canvas/);
  }
  assert.equal(module.calls,0);
  const source=await readFile('src/pages/shared/LivePoseGuide.jsx','utf8');
  assert.doesNotMatch(source,/getUserMedia|MediaPipe|useEffect|livePose|api\./);
  const {onboardingDestination}=await import('../src/utils/onboarding.js');
  assert.equal(onboardingDestination('completed','/owner/live-pose'),null);
  assert.equal(onboardingDestination('pending_studio','/owner/live-pose'),'/owner/studio-setup');
  assert.equal(onboardingDestination('pending_plan','/owner/live-pose'),'/owner/subscription');
} finally {await rm(temporary,{recursive:true,force:true});}
