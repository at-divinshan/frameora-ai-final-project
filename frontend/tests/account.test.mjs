// Isolated checks: no backend requests, database access, or real authentication.
// Run: node tests/account.test.mjs (from frontend).
import { build } from 'esbuild';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';
const directory = await mkdtemp(path.join(tmpdir(), 'frameora-account-'));
const source = `
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import assert from 'node:assert/strict';
import { validateProfile, validatePicture } from './src/utils/profile';
import api from './src/services/api';
import { updateProfile, updatePrivacy, uploadProfilePicture, getProfilePicture } from './src/services/userService';
import { AuthContext } from './src/context/AuthContext';
import { ThemeProvider } from './src/context/ThemeContext';
import AppRoutes from './src/routes/AppRoutes';
import { AccountSecurity } from './src/components/common/AccountSettings';
import { getOnboarding, saveStudio } from './src/services/ownerService';
import { guardStudioNavigation, studioPhotoNotice, studioSaveDestination, onboardingDestination, validateStudio } from './src/utils/onboarding';
import { saveStudioDetails } from './src/pages/owner/StudioSetup';
import Landing from './src/pages/public/Landing';
import AdminLayout from './src/components/layout/AdminLayout';
import { OwnerFacts, AdminMetrics, onboardingLabel } from './src/pages/admin/Dashboard';
import { getAdminOwners } from './src/services/adminService';
import { PlanCards } from './src/pages/owner/Subscription';
import { StudioDetails } from './src/pages/owner/Dashboard';
import { watchSubscriptionRefresh, activationDisabled, activationConfirmed, validateStudioPhoto, utcDate, ownerError } from './src/utils/subscription';
import { activatePlan, uploadStudioPhoto } from './src/services/ownerService';
export function lockedHero() {
 const html=renderToStaticMarkup(<AuthContext.Provider value={{user:null}}><ThemeProvider><MemoryRouter><Landing /></MemoryRouter></ThemeProvider></AuthContext.Provider>);
 const hero=html.slice(html.indexOf('<section'),html.indexOf('</section>'));
 const plain=hero.replace(/<[^>]+>/g,'');
 for(const text of ['AI POWERED PHOTOGRAPHY PLATFORM','Create Beautiful Moments with AI','From shoot planning to pose ideas and AI-generated visuals, Frameora AI helps you capture every moment better.','Get Started','Login']) assert.ok(plain.includes(text),text);
 assert.ok(hero.includes('href="/register"')); assert.ok(hero.includes('href="/login"'));
 assert.ok(hero.includes('/images/landing/hero-dark.png'));
 assert.ok(!hero.includes('Turn Your Moments'));
}
export function adminNavigation() {
 for (const path of ['/admin/dashboard','/admin/dashboard#studio-owners','/admin/profile','/admin/settings']) {
  const html=renderToStaticMarkup(<AuthContext.Provider value={{user:{id:3,name:'Admin',role:'admin'}}}><ThemeProvider><MemoryRouter initialEntries={[path]}><AdminLayout /></MemoryRouter></ThemeProvider></AuthContext.Provider>);
  const nav=html.slice(html.indexOf('<nav'),html.indexOf('</nav>'));
  assert.equal((nav.match(/class="admin-nav-item is-active"/g)||[]).length,1,path);
  const active=nav.match(/<a[^>]*class="admin-nav-item is-active"[^>]*>/)[0];
  assert.ok(active.includes('href="'+path+'"'),active);
  assert.ok(active.includes('aria-current="page"'));
  assert.ok(nav.includes('Projects — coming soon'));
 }
}
export function adminMetricsAndLabels() {
 const html=renderToStaticMarkup(<AdminMetrics summary={{normal_users:17,studio_owners:0}} />);
 assert.ok(html.includes('admin-summary-count')); assert.ok(html.includes('>17<')); assert.ok(html.includes('>0<'));
 assert.ok(renderToStaticMarkup(<AdminMetrics />).includes('Loading'));
 assert.ok(renderToStaticMarkup(<AdminMetrics error="offline" />).includes('Unavailable'));
 assert.equal(onboardingLabel('pending_studio'),'Pending Studio');
 assert.equal(onboardingLabel('pending_plan'),'Pending Plan');
 assert.equal(onboardingLabel('completed'),'Completed');
 assert.equal(onboardingLabel('unexpected'),'Unknown');
}
export function adminDashboardGuard() {
 for(const role of [null,'user','owner','admin']) {
  const user=role?{id:3,name:'Fixture',role}:null;
  const html=renderToStaticMarkup(<AuthContext.Provider value={{user,loading:false}}><ThemeProvider><MemoryRouter initialEntries={['/admin/dashboard']}><AppRoutes /></MemoryRouter></ThemeProvider></AuthContext.Provider>);
  if(role==='admin') { assert.ok(html.includes('Studio Owner management')); assert.ok(html.includes('Loading Studio Owners')); }
  else assert.equal(html,'');
 }
}
export function adminMapping() {
 const html=renderToStaticMarkup(<OwnerFacts owner={{name:'Owner Name',email:'owner@example.invalid',created_at:'2026-01-01T00:00:00',onboarding_status:'pending_studio',studio:null,subscription:null,subscription_status:'unavailable'}} />);
 for(const text of ['Owner Name','owner@example.invalid','Not provided','Unavailable','Pending Studio']) assert.ok(html.includes(text));
 assert.ok(!html.includes('Approve')); assert.ok(!html.includes('password_hash'));
}
export async function adminRequests() {
 let sent; api.defaults.adapter=async config=>{sent=config;return {data:{items:[],total:0,page:1,page_size:20},status:200,headers:{},config};};
 const result=await getAdminOwners({q:'Jaffna',page:1,page_size:20});
 assert.equal(result.total,0); assert.equal(sent.url,'/admin/owners'); assert.equal(sent.params.q,'Jaffna');
}
export function studioSprint() {
 for(const phone of ['0771234567','+94771234567']) assert.deepEqual(validateStudio({studio_name:'Studio',studio_phone:phone,studio_address:'1 Road',studio_city:'Jaffna'}),{});
 for(const path of ['/owner/subscription','/owner/studio-setup','/owner/dashboard']) assert.equal(onboardingDestination('completed',path),null);
 assert.throws(()=>onboardingDestination('unknown','/owner/dashboard'));
 assert.equal(validateStudioPhoto({type:'image/webp',size:1024}),'');
 assert.ok(validateStudioPhoto({type:'image/svg+xml',size:1024}));
 assert.ok(validateStudioPhoto({type:'image/png',size:5242881}));
 assert.equal(activationDisabled({code:'trial',activation_available:true},{plan:'basic',trial_available:true}),false);
 assert.equal(activationDisabled({code:'trial',activation_available:true},{plan:'basic',trial_available:false}),true);
 assert.equal(activationDisabled({code:'pro',activation_available:true},{plan:'basic'}),true);
 assert.equal(activationDisabled({code:'basic',activation_available:true},{plan:'trial'}),true);
 assert.equal(activationConfirmed({plan:'basic'},{onboarding_status:'completed'}),true);
 assert.equal(activationConfirmed({plan:'basic'},{onboarding_status:'pending_plan'}),false);
 assert.equal(activationConfirmed({plan:null},{onboarding_status:'completed'}),false);
 assert.equal(utcDate(null),'Unavailable');
 assert.equal(ownerError({response:{data:{detail:'Migration unavailable'}}},'Fallback'),'Migration unavailable');
}
export function subscriptionRefresh() {
 let refreshes=0, delay, callback, cleared;
 const events=new Map(), visibility=new Map();
 const browser={document:{hidden:false,addEventListener:(k,f)=>visibility.set(k,f),removeEventListener:k=>visibility.delete(k)},
 addEventListener:(k,f)=>events.set(k,f),removeEventListener:k=>events.delete(k),
 setTimeout:(fn,ms)=>{callback=fn;delay=ms;return 7;},clearTimeout:id=>{cleared=id;}};
 const cleanup=watchSubscriptionRefresh('2026-01-15T12:00:00',()=>refreshes++,browser,Date.parse('2026-01-15T11:00:00Z'));
 assert.equal(delay,3601000); callback(); assert.equal(refreshes,1);
 browser.document.hidden=true; visibility.get('visibilitychange')(); assert.equal(refreshes,1);
 browser.document.hidden=false; visibility.get('visibilitychange')(); events.get('focus')(); assert.equal(refreshes,3);
 cleanup(); assert.equal(cleared,7); assert.equal(events.size,0); assert.equal(visibility.size,0);
 watchSubscriptionRefresh('2026-01-15T12:00:00Z',()=>{},browser,Date.parse('2026-01-16T12:00:00Z'))(); assert.equal(delay,30000);
 callback=null; watchSubscriptionRefresh(undefined,()=>{},browser)(); assert.equal(callback,null);
 watchSubscriptionRefresh('invalid',()=>{},browser)(); assert.equal(callback,null);
}
export function planRendering() {
 const plans=[{code:'basic',name:'Free Basic',price:'0',currency:'LKR',credits:10,max_projects:2,max_share_links:3,activation_available:true},
 {code:'trial',name:'Free Trial',price:'0',currency:'LKR',credits:100,max_projects:10,max_share_links:20,trial_days:14,credit_period:'trial_total',activation_available:true},
 {code:'pro',name:'Paid Pro',price:'1500',currency:'LKR',credits:500,max_projects:50,max_share_links:100,activation_available:false}];
 const html=renderToStaticMarkup(<PlanCards plans={plans} status={{plan:'basic',trial_available:true}} activate={()=>{}} />);
 for(const text of ['Free Basic','Free Trial','Paid Pro','Start Free Trial','Current plan','Paid activation unavailable','100 credits total','14 days','no carryover']) assert.ok(html.includes(text),text);
 const used=renderToStaticMarkup(<PlanCards plans={plans} status={{plan:'basic',trial_available:false}} activate={()=>{}} />);
 assert.ok(used.includes('lifetime trial has already been used'));
}
export function studioRendering() {
 const html=renderToStaticMarkup(<MemoryRouter><StudioDetails studio={{studio_name:'Real Studio',studio_phone:'0771234567',studio_address:'10 Road',studio_city:'Jaffna',studio_description:'Photography'}} /></MemoryRouter>);
 for(const text of ['Real Studio','0771234567','10 Road','Jaffna','Photography']) assert.ok(html.includes(text));
 assert.ok(renderToStaticMarkup(<MemoryRouter><StudioDetails studio={null} /></MemoryRouter>).includes('unavailable'));
}
export async function activationRequests() {
 const sent=[]; api.defaults.adapter=async config=>{sent.push(config);return {data:{plan:'basic'},status:200,headers:{},config};};
 await activatePlan('basic','same-request-key'); await activatePlan('basic','same-request-key');
 assert.deepEqual(JSON.parse(sent[0].data),JSON.parse(sent[1].data));
 assert.equal(sent[0].url,'/owner/subscription/basic');
 assert.throws(()=>activatePlan('pro','key'));
 const file=new Blob(['test'],{type:'image/webp'}); await uploadStudioPhoto(file);
 assert.equal(sent[2].data,file); assert.equal(sent[2].headers.get('Content-Type'),'image/webp');
}

export async function validation() {
 assert.deepEqual(validateProfile({name:' Alice ',phone:'+94 (77) 123-4567'}),{});
 assert.ok(validateProfile({name:'A',phone:'abc'}).name);
 assert.ok(validateProfile({name:'Alice',phone:'123'}).phone);
 assert.ok(validateProfile({name:'A\\u0000B',phone:''}).name);
 assert.deepEqual(validateProfile({name:'Alice',phone:''}),{});
 assert.equal(validatePicture({type:'image/png',size:5*1024*1024}),'');
 assert.ok(validatePicture({type:'image/png',size:5*1024*1024+1}));
 assert.ok(validatePicture({type:'image/svg+xml',size:100}));
 assert.ok(validatePicture({type:'image/jpeg',size:0}));
}
export async function ownerOnboarding() {
 const valid={studio_name:'Test Studio',studio_phone:'+94 77 123 4567',studio_address:'1 Test Road',studio_city:'Jaffna',studio_description:''};
 assert.deepEqual(validateStudio(valid),{});
 assert.ok(validateStudio({...valid,studio_name:' '}).studio_name);
 assert.ok(validateStudio({...valid,studio_phone:'123'}).studio_phone);
 assert.ok(validateStudio({...valid,studio_address:'a'}).studio_address);
 assert.ok(validateStudio({...valid,studio_city:'a'}).studio_city);
 assert.ok(validateStudio({...valid,studio_description:'x'.repeat(2001)}).studio_description);
 assert.ok(validateStudio({...valid,studio_description:'bad\\u0000text'}).studio_description);
 assert.deepEqual(validateStudio({...valid,studio_description:'Line one\\nLine two\\t'}),{});
 assert.equal(onboardingDestination('pending_studio','/owner/dashboard'),'/owner/studio-setup');
 assert.equal(onboardingDestination('pending_studio','/owner/studio-setup'),null);
 assert.equal(onboardingDestination('pending_plan','/owner/studio-setup'),null);
 assert.equal(onboardingDestination('pending_plan','/owner/dashboard'),'/owner/subscription');
 assert.equal(onboardingDestination('pending_plan','/owner/subscription'),null);
 assert.equal(onboardingDestination('completed','/owner/subscription'),null);
 assert.equal(onboardingDestination('completed','/owner/dashboard'),null);
 assert.equal(onboardingDestination('completed','/owner/profile'),null);
 let calls=0;
 const ownerId='onboarding-cache-test';
 api.defaults.adapter=async config=>{ calls++; return {data:config.url==='/owner/studio'?{onboarding_status:'pending_plan'}:{onboarding_status:'pending_studio'},status:200,statusText:'OK',headers:{},config}; };
 const [first,second]=await Promise.all([getOnboarding(ownerId),getOnboarding(ownerId)]);
 assert.deepEqual(first,second);
 assert.equal(calls,1);
 await getOnboarding(ownerId);
 assert.equal(calls,2);
 assert.deepEqual(await saveStudio({}),{onboarding_status:'pending_plan'});
 assert.equal(calls,3);
}
export async function studioContextRefresh() {
 const published=[];
 api.defaults.adapter=async config=>({data:{onboarding_status:'pending_plan',studio:JSON.parse(config.data)},status:200,headers:{},config});
 const result=await saveStudioDetails({studio_name:' Studio ',studio_description:' '}, value=>published.push(value));
 assert.equal(published.length,1); assert.equal(published[0],result);
 assert.deepEqual(result.studio,{studio_name:'Studio',studio_description:null});
 api.defaults.adapter=async()=>{throw new Error('Save failed');};
 await assert.rejects(saveStudioDetails({studio_name:'Studio'}, value=>published.push(value)));
 assert.equal(published.length,1,'Failed saves must not publish state');
}
export function studioSaveRouting() {
 assert.equal(studioSaveDestination('completed'),'/owner/dashboard');
 for (const status of ['pending_studio','pending_plan']) assert.equal(studioSaveDestination(status),'/owner/subscription');
 assert.equal(onboardingDestination('pending_plan','/owner/studio-setup'),null);
 assert.equal(onboardingDestination('pending_plan','/owner/dashboard'),'/owner/subscription');
 assert.equal(onboardingDestination('pending_studio','/owner/subscription'),'/owner/studio-setup');
}
export function studioNavigationSafety() {
 let state={pending:false,busy:false}, notices=0, navigations=0;
 const handlers=new Map(), moves=[];
 const navigator={push(){navigations++;},replace(){navigations++;},go(){navigations++;}};
 const original={...navigator};
 const browser={history:{state:{idx:3},go(delta){moves.push(delta);}},addEventListener(name,fn){handlers.set(name,fn);},removeEventListener(name,fn){assert.equal(handlers.get(name),fn);handlers.delete(name);}};
 const cleanup=guardStudioNavigation(navigator,browser,()=>Boolean(studioPhotoNotice(state)),()=>notices++);
 navigator.push('/owner/dashboard'); assert.equal(navigations,1);
 for(const blocked of [{pending:true,busy:false},{pending:true,busy:true},{pending:false,busy:true}]) {
  state=blocked; assert.ok(studioPhotoNotice(state));
  navigator.push('/owner/dashboard'); navigator.replace('/owner/subscription'); navigator.go(-1);
  assert.equal(navigations,1);
  let prevented=false; const event={preventDefault(){prevented=true;}};
  handlers.get('beforeunload')(event); assert.equal(prevented,true); assert.equal(event.returnValue,'');
 }
 assert.equal(notices,9);
 let stopped=0; browser.history.state.idx=2;
 handlers.get('popstate')({stopImmediatePropagation(){stopped++;}});
 assert.deepEqual(moves,[1]); assert.equal(stopped,1);
 browser.history.state.idx=3;
 handlers.get('popstate')({stopImmediatePropagation(){stopped++;}}); assert.equal(stopped,2);
 state={pending:false,busy:false}; assert.equal(studioPhotoNotice(state),'');
 navigator.replace('/owner/dashboard'); assert.equal(navigations,2);
 cleanup(); assert.equal(handlers.size,0);
 for(const method of ['push','replace','go']) assert.equal(navigator[method],original[method]);
}
export async function payloads() {
 let sent;
 api.defaults.adapter = async config => { sent=config; return {data:{},status:200,statusText:'OK',headers:{},config}; };
 await updateProfile({name:' Alice ',phone:' ',role:'admin',email:'ignored'});
 assert.deepEqual(JSON.parse(sent.data),{name:'Alice',phone:null});
 const privacy={profile_visibility:'public',photography_plans_default:'private',ai_images_default:'private',role:'admin'};
 await updatePrivacy(privacy,'user'); assert.deepEqual(Object.keys(JSON.parse(sent.data)).sort(),['ai_images_default','photography_plans_default','profile_visibility']);
 await updatePrivacy(privacy,'admin'); assert.equal(JSON.parse(sent.data).profile_visibility,undefined);
 const file=new Blob(['isolated fixture'],{type:'image/png'}); await uploadProfilePicture(file);
 assert.equal(sent.data,file); assert.equal(sent.headers.get('Content-Type'),'image/png'); assert.equal(sent.url,'/users/me/picture');
 api.defaults.adapter=async config=>({data:new Blob(['png'],{type:'image/png'}),status:200,headers:{},config});
 assert.equal((await getProfilePicture()).type,'image/png');
 api.defaults.adapter=async()=>{throw {response:{status:404}}}; assert.equal(await getProfilePicture(),null);
 api.defaults.adapter=async config=>({data:new Blob(['html'],{type:'text/html'}),status:200,headers:{},config});
 await assert.rejects(getProfilePicture());
}
export function security() {
 for (const role of ['user','owner','admin']) for (const has_password of [false,true]) for (const google_linked of [false,true]) {
  const html=renderToStaticMarkup(<MemoryRouter><AccountSecurity profile={{role,has_password,google_linked}} /></MemoryRouter>);
  if(role==='admin') assert.ok(!html.includes('Google'));
  if(has_password || role!=='admin') assert.ok(html.includes('disabled=""'));
  assert.equal(html.includes('href="/auth/google/link"'),role!=='admin' && has_password && !google_linked);
  assert.ok(!html.includes('type="password"'));
 }
}
export function route(role,target,page) {
 const user=role ? {id:'disposable-fixture',name:'Test Account',role} : null;
 const html=renderToStaticMarkup(<AuthContext.Provider value={{user,loading:false,refreshProfile:()=>{},refreshPicture:()=>{}}}><ThemeProvider><MemoryRouter initialEntries={['/'+target+'/'+page]}><AppRoutes /></MemoryRouter></ThemeProvider></AuthContext.Provider>);
 if(role!==target) { assert.equal(html,''); return; }
 assert.ok(html.includes('href="/'+role+'/profile"'));
 assert.ok(html.includes('href="/'+role+'/settings"'));
 assert.ok(html.includes(page==='profile' ? 'Loading profile' : 'Loading privacy settings'));
 if(role==='admin') assert.ok(!html.includes('Link Google account'));
}
`;
const result = await build({stdin:{contents:source,resolveDir:process.cwd(),loader:'jsx'},bundle:true,write:false,platform:'node',format:'esm',packages:'external',jsx:'automatic',loader:{'.css':'empty'},define:{'import.meta.env':'{}'}});
// Keep external dependencies resolvable from the existing frontend installation.
const file = path.join(directory,'checks.mjs');
const { symlink } = await import('node:fs/promises');
await symlink(path.resolve('node_modules'),path.join(directory,'node_modules'));
await writeFile(file,result.outputFiles[0].text);
const checks=await import(pathToFileURL(file));
test('locked landing hero and navigation',checks.lockedHero);
test('Admin sidebar has exactly one active link including hash navigation',checks.adminNavigation);
test('Admin metrics use real values, loading/error states and readable labels',checks.adminMetricsAndLabels);
test('Admin dashboard role guard and loading state',checks.adminDashboardGuard);
test('Admin detail mapping and unavailable state',checks.adminMapping);
test('Admin search API request',checks.adminRequests);
test('studio validation, eligibility, migration errors and redirect confirmation',checks.studioSprint);
test('dashboard entitlement refresh uses UTC boundaries, focus and cleans up',checks.subscriptionRefresh);
test('subscription cards and trial-used state',checks.planRendering);
test('dashboard studio mapping and unavailable state',checks.studioRendering);
test('activation retries and raw studio uploads',checks.activationRequests);
test('studio saves publish server onboarding state only after success',checks.studioContextRefresh);
test('studio edits preserve onboarding gates and completed save destination',checks.studioSaveRouting);
test('unsaved photos and running uploads block navigation and unload, then release safely',checks.studioNavigationSafety);
test('profile and file validation',checks.validation);
test('owner onboarding validation, redirects, and request deduplication',checks.ownerOnboarding);
test('password controls disabled and Google controls excluded for Admin',checks.security);
test('API allowlists, raw uploads and safe image responses',checks.payloads);
for(const role of [null,'user','owner','admin']) for(const target of ['user','owner','admin']) for(const page of ['profile','settings']) {
 test((role||'anonymous')+' → '+target+'/'+page,()=>checks.route(role,target,page));
}
test.after(()=>rm(directory,{recursive:true,force:true}));
