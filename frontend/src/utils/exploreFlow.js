import {getExploreSample} from '../data/exploreSamples';

export function sessionStore() { try { return window.sessionStorage; } catch { return null; } }
export function validPlanId(value) { return /^[1-9]\d*$/.test(String(value || '')) ? String(value) : null; }
export function sceneMode(value) { return value === 'scene' ? 'scene' : 'inspiration'; }
export function readDraft(storage, key, defaults) {
  try {
    const saved=JSON.parse(storage.getItem(key));
    const values={...defaults};
    for (const name of Object.keys(defaults)) if (typeof saved?.values?.[name] === 'string' && saved.values[name].length <= 2000) values[name]=saved.values[name];
    return {values,mode:sceneMode(saved?.mode)};
  } catch { return {values:{...defaults},mode:'inspiration'}; }
}
export function writeSession(storage,key,value) { try { storage.setItem(key,JSON.stringify(value)); return true; } catch { return false; } }
export function planContextKey(userId,planId) { return `frameora.explore.plan.${userId}.${planId}`; }
export function readPlanContext(storage,userId,planId) {
  if (!validPlanId(planId)) return null;
  try { const data=JSON.parse(storage.getItem(planContextKey(userId,planId))); return getExploreSample(data?.sampleId) ? {sampleId:data.sampleId,mode:sceneMode(data.mode)} : null; } catch { return null; }
}
export async function loadSampleScene(sampleId, signal, fetcher=fetch) {
  const sample=getExploreSample(sampleId);
  if (!sample) throw new Error('This sample image is unavailable.');
  // Only catalogued same-origin paths are fetched. Never accept a URL from route state.
  const response=await fetcher(sample.image,{signal,credentials:'same-origin',redirect:'error'});
  if (!response.ok) throw new Error('The sample image could not be loaded. You can still use inspiration only.');
  const blob=await response.blob();
  if (blob.type !== 'image/png' || blob.size === 0 || blob.size > 5*1024*1024) throw new Error('The sample must be a PNG image of at most 5 MiB.');
  return new File([blob],`${sample.id}.png`,{type:'image/png'});
}
