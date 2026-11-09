import { createProject, createProjectPlan, getProjects, getProjectPlans } from './projectService';

const api = { createProject, createProjectPlan, getProjects, getProjectPlans };
const canonical = value => JSON.stringify(value, function (key, item) {
  return item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(k => [k, item[k]])) : item;
});
export function matchesPhotoshootRecord(record, payload) {
  return Object.entries(payload).every(([key, value]) => {
    let actual = record[key];
    if (key === 'preferences' && typeof actual === 'string') {
      try { actual = JSON.parse(actual); } catch { return false; }
    }
    return canonical(actual ?? null) === canonical(value ?? null);
  });
}

// Projects/plans have no idempotency key. An uncertain POST must be reconciled by
// reads, never automatically repeated. Generation retains its existing key flow.
export async function savePhotoshoot(progress, projectPayload, planPayload, checkpoint, services = api) {
  let state = { ...progress };
  const record = update => { state = { ...state, ...update }; checkpoint(state); };
  for (const step of ['project', 'plan']) {
    const idField = `${step}Id`;
    if (state[idField]) continue;
    const payload = step === 'project' ? projectPayload : planPayload;
    const list = () => step === 'project' ? services.getProjects() : services.getProjectPlans(state.projectId);
    if (state.pendingStep === step) {
      const candidates = (await list()).filter(item => !state.beforeIds.includes(item.id) && matchesPhotoshootRecord(item, state.pendingPayload));
      if (candidates.length !== 1) throw new Error('The previous save could not be confirmed. Check your saved photoshoots, then check again here. No duplicate request was sent.');
      record({ [idField]: candidates[0].id, pendingStep: null, beforeIds: null, pendingPayload: null });
      continue;
    }
    const existing = await list();
    record({ pendingStep: step, beforeIds: existing.map(item => item.id), pendingPayload: payload });
    let saved;
    try {
      saved = step === 'project' ? await services.createProject(payload) : await services.createProjectPlan(state.projectId, payload);
    } catch (error) {
      const status = error.response?.status;
      if (status >= 400 && status < 500 && ![408, 429].includes(status)) record({ pendingStep: null, beforeIds: null, pendingPayload: null });
      throw error;
    }
    record({ [idField]: saved.id, pendingStep: null, beforeIds: null, pendingPayload: null });
  }
  return state;
}
