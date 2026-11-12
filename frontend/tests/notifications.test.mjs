import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
const temporary=await mkdtemp(path.join(process.cwd(),'tests/.notifications-'));
try {
 const outfile=path.join(temporary,'bundle.mjs');
 await build({stdin:{contents:`export * from './src/services/notificationService';export {default as api} from './src/services/api';export {NotificationItems} from './src/components/common/NotificationBell';export {default as Sidebar} from './src/components/layout/Sidebar';export {onboardingDestination} from './src/utils/onboarding';`,resolveDir:process.cwd()},bundle:true,format:'esm',platform:'node',packages:'external',loader:{'.css':'empty'},jsx:'automatic',outfile,define:{'import.meta.env':'{}'}});
 const m=await import(pathToFileURL(outfile));const calls=[];
 m.api.defaults.adapter=async config=>{calls.push(config);return {data:{items:[],unread_count:0},status:200,headers:{},config};};
 const signal=new AbortController().signal;await m.getNotifications(17,signal);await m.markNotification(9);
 assert.equal(calls[0].url,'/notifications');assert.equal(calls[0].params.before,17);assert.equal(calls[0].signal,signal);
 assert.deepEqual(JSON.parse(calls[1].data),{is_read:true});
 for(const href of ['https://bad.test','//bad.test','javascript:alert(1)','/owner/projects/1?token=secret'])assert.equal(m.safeNotificationLink(href),null);
 assert.equal(m.safeNotificationLink('/owner/projects/1#feedback-2'),'/owner/projects/1#feedback-2');
 const html=renderToStaticMarkup(React.createElement(MemoryRouter,null,React.createElement(m.NotificationItems,{items:[{id:1,message:'<script>unsafe</script>',created_at:'2026-11-11T00:00:00Z',href:'https://bad.test',is_read:false}],onRead:()=>{}})));
 assert.match(html,/&lt;script&gt;/);assert.match(html,/Mark Read/);assert.doesNotMatch(html,/href="https/);
 const mixed=renderToStaticMarkup(React.createElement(MemoryRouter,null,React.createElement(m.NotificationItems,{items:[{id:1,message:'Already read',is_read:true},{id:2,message:'New message',is_read:false,created_at:'2026-11-11T00:00:00Z'}],onRead:()=>{}})));
 assert.doesNotMatch(mixed,/Already read|Mark unread|Mark Unread/);assert.match(mixed,/New message/);
 const state={items:[{id:1,is_read:false},{id:2,is_read:false}],unread_count:2,next_before:2};
 const removed=m.withoutNotifications(state,new Set([1]));assert.equal(removed.unread_count,1);assert.deepEqual(removed.items.map(n=>n.id),[2]);assert.equal(state.items.length,2);
 assert.equal(m.withoutNotifications(removed,new Set([2])).unread_count,0);
 globalThis.window=new EventTarget();const events=[];window.addEventListener('notification-read',e=>events.push(e.detail.phase));
 let finish; m.api.defaults.adapter=config=>new Promise(resolve=>{finish=()=>resolve({data:{id:2,is_read:true},status:200,headers:{},config});});
 const request=m.readNotification(2,1);assert.deepEqual(events,['start']);assert.equal(m.readNotification(2,1),request);
 await new Promise(resolve=>setTimeout(resolve,0));finish();await request;assert.deepEqual(events,['start','success']);
 events.length=0;m.api.defaults.adapter=async()=>{throw new Error('offline');};await assert.rejects(m.readNotification(3,1));assert.deepEqual(events,['start','failure']);delete globalThis.window;
 for(const file of ['components/common/NotificationBell.jsx','pages/shared/Notifications.jsx']){
   const source=await readFile(`src/${file}`,'utf8');assert.match(source,/No new notifications/);assert.doesNotMatch(source,/Mark unread|Mark Unread/);
 }
 assert.equal(m.onboardingDestination('completed','/owner/notifications'),null);
 assert.equal(m.onboardingDestination('pending_studio','/owner/notifications'),'/owner/studio-setup');
 const sidebar=await readFile('src/components/layout/Sidebar.jsx','utf8');
 assert.match(sidebar,/path \|\| label === "My Plans"/);assert.match(sidebar,/\/user\/notifications/);
 for(const file of ['Sidebar','AdminLayout','OwnerLayout'])assert.doesNotMatch(await readFile(`src/components/layout/${file}.jsx`,'utf8'),/label: "(?:Bookings|My Bookings|Equipment)"/);
}finally{await rm(temporary,{recursive:true,force:true});}
