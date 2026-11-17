
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {dismissWithEscape} from '../src/utils/keyboardDismiss.js';

test('Escape dismisses an open disclosure and restores trigger focus once',()=>{
  const calls=[];
  const event={key:'Escape',preventDefault:()=>calls.push('prevent'),stopPropagation:()=>calls.push('stop')};
  dismissWithEscape(event,true,()=>calls.push('close'),{current:{focus:()=>calls.push('focus')}});
  assert.deepEqual(calls,['prevent','stop','close','focus']);
  for(const e of [{key:'Tab'},{key:'Escape',defaultPrevented:true}]) dismissWithEscape(e,true,()=>assert.fail(),{});
  dismissWithEscape({key:'Escape'},false,()=>assert.fail(),{});
});
test('mobile navigation dismissal does not affect desktop navigation',()=>{
  const previous=globalThis.window;
  try {
    for(const matches of [false,true]) {
      let closes=0,focuses=0;
      globalThis.window={matchMedia:query=>{assert.equal(query,'(max-width: 760px)');return {matches};}};
      dismissWithEscape({key:'Escape',preventDefault(){},stopPropagation(){}},true,()=>closes++,{current:{focus:()=>focuses++}},true);
      assert.equal(closes,Number(matches));assert.equal(focuses,Number(matches));
    }
  }finally{if(previous===undefined)delete globalThis.window;else globalThis.window=previous;}
});
test('components wire local dismissal; loading and dialog safeguards remain present',async()=>{
  for(const path of ['components/layout/Sidebar.jsx','components/layout/AdminLayout.jsx','components/common/NotificationBell.jsx']){
    const source=await readFile('src/'+path,'utf8');
    assert.match(source,/onKeyDown=.*dismissWithEscape/);assert.match(source,/ref=\{(?:menuTrigger|trigger)\}/);
  }
  const routes=await readFile('src/routes/AppRoutes.jsx','utf8');
  assert.match(routes,/if \(loading\) return <div className="auth-session-loading" role="status"/);
  const css=await readFile('src/styles/dashboard.css','utf8');
  assert.match(css,/max-height: calc\(100dvh - 40px\); overflow-y: auto/);
  const dialog=await readFile('src/components/photography/PlanDeleteDialog.jsx','utf8');
  assert.match(dialog,/onKeyDown=\{handleKeyDown\}/);assert.match(dialog,/aria-modal="true"/);
});
