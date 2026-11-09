import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';
import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const temporary = await mkdtemp(path.join(process.cwd(), 'tests/.photoshoot-'));
try {
  const outfile = path.join(temporary, 'bundle.mjs');
  await build({ stdin: { contents: `export * from './src/services/photoshootService';
    export {default as PhotoshootForm, initialPhotoshoot, validatePhotoshoot, photoshootPayloads} from './src/components/projects/PhotoshootForm';`, resolveDir: process.cwd() },
    bundle: true, format: 'esm', platform: 'node', packages: 'external', jsx: 'automatic', outfile,
    define: { 'import.meta.env': JSON.stringify({ VITE_API_URL: 'http://localhost:8000' }) } });
  const m = await import(pathToFileURL(outfile));
  const values = { ...m.initialPhotoshoot, customer_name: 'Ana', project_title: 'Portrait session', photography_type: 'Portrait', shooting_date: '2026-11-12', shoot_time: '09:00',
    customization: { ...m.initialPhotoshoot.customization, outfit_mode: 'custom', outfit_details: 'Blue suit' } };
  const payload = m.photoshootPayloads(values);
  const mockServices = (calls = []) => ({
    getProjects: async () => [], getProjectPlans: async () => [],
    createProject: async body => { calls.push(['project', body]); return { id: 3 }; },
    createProjectPlan: async (id, body) => { calls.push(['plan', id, body]); return { id: 7 }; },
  });
  test('one form saves project then linked plan and checkpoints both IDs', async () => {
    const calls = [], states = [];
    const result = await m.savePhotoshoot({}, payload.project, payload.plan, state => states.push(state), mockServices(calls));
    assert.deepEqual(calls, [['project', payload.project], ['plan', 3, payload.plan]]);
    assert.equal(result.projectId, 3); assert.equal(result.planId, 7);
    assert.equal(states[0].pendingStep, 'project');
    assert.equal(states[1].projectId, 3);
    assert.equal(states[2].pendingStep, 'plan');
    assert.equal(states.at(-1).pendingStep, null);
    await m.savePhotoshoot(result, payload.project, payload.plan, () => {}, mockServices(calls));
    assert.equal(calls.length, 2, 'completed saves do not create duplicates');
  });
  test('a rejected plan save resumes without creating the customer project again', async () => {
    const calls = []; let state = {};
    const services = mockServices(calls);
    services.createProjectPlan = async () => { throw { response: { status: 422 } }; };
    await assert.rejects(m.savePhotoshoot(state, payload.project, payload.plan, next => { state = next; }, services));
    assert.equal(state.projectId, 3); assert.equal(state.pendingStep, null);
    const resumed = await m.savePhotoshoot(state, payload.project, payload.plan, next => { state = next; }, mockServices(calls));
    assert.equal(resumed.planId, 7);
    assert.equal(calls.filter(([kind]) => kind === 'project').length, 1);
  });
  test('lost project response is reconciled by a read, never a repeated POST', async () => {
    const calls = []; let state = {};
    const services = mockServices(calls);
    services.createProject = async () => { calls.push(['lost-project']); throw new Error('Network response lost'); };
    await assert.rejects(m.savePhotoshoot(state, payload.project, payload.plan, next => { state = next; }, services));
    assert.equal(state.pendingStep, 'project');
    services.getProjects = async () => [{ id: 3, ...payload.project }];
    const result = await m.savePhotoshoot(state, payload.project, payload.plan, next => { state = next; }, services);
    assert.equal(result.projectId, 3); assert.equal(result.planId, 7);
    assert.equal(calls.filter(([kind]) => kind === 'lost-project').length, 1);
  });
  test('uncertain or ambiguous saves stay blocked and a storage failure prevents POST', async () => {
    const state = { pendingStep: 'project', beforeIds: [], pendingPayload: payload.project };
    for (const records of [[], [{ id: 1, ...payload.project }, { id: 2, ...payload.project }]]) {
      const calls = [], services = mockServices(calls);
      services.getProjects = async () => records;
      await assert.rejects(m.savePhotoshoot(state, payload.project, payload.plan, () => {}, services), /No duplicate request/);
      assert.equal(calls.length, 0);
    }
    const calls = [];
    await assert.rejects(m.savePhotoshoot({}, payload.project, payload.plan, () => { throw new Error('Storage unavailable'); }, mockServices(calls)), /Storage unavailable/);
    assert.equal(calls.length, 0);
  });
  test('lost plan response recovers saved customization and does not repeat creation', async () => {
    const state = { projectId: 3, pendingStep: 'plan', beforeIds: [2], pendingPayload: payload.plan };
    const calls = [], services = mockServices(calls);
    services.getProjectPlans = async () => [{ id: 2, ...payload.plan }, { id: 7, ...payload.plan, preferences: JSON.stringify(payload.plan.preferences) }];
    const result = await m.savePhotoshoot(state, payload.project, payload.plan, () => {}, services);
    assert.equal(result.planId, 7); assert.equal(calls.length, 0);
    assert.equal(payload.plan.shoot_datetime, '2026-11-12T09:00:00');
    assert.equal(payload.plan.preferences.owner_generation.outfit_details, 'Blue suit');
    assert.ok(!('customization' in payload.project));
  });
  test('photoshoot form validates custom settings and exposes both save choices without automatic generation', () => {
    assert.deepEqual(m.validatePhotoshoot(values), {});
    assert.ok(m.validatePhotoshoot({ ...values, customer_name: '  ' }).customer_name);
    assert.ok(m.validatePhotoshoot({ ...values, customization: { ...values.customization, outfit_details: '' } }).outfit_details);
    const html = renderToStaticMarkup(React.createElement(m.PhotoshootForm, { values, errors: {}, progress: {}, canCreate: true, referenceName: 'portrait.png' }));
    for (const label of ['Customer', 'Photography plan', 'Image customization', 'Save Photoshoot', 'Save &amp; Generate 2 Images', 'confirm the 2-credit charge', 'Reference photo']) assert.ok(html.includes(label), label);
    assert.equal((html.match(/<form/g) || []).length, 1);
    assert.match(html, /name="background_mode"/);
    assert.match(html, /name="camera_angle_mode"/);
    const busy = renderToStaticMarkup(React.createElement(m.PhotoshootForm, { values, errors: {}, progress: { projectId: 3 }, busy: true, canCreate: true }));
    assert.match(busy, /fieldset[^>]*disabled/);
  });
} finally { await rm(temporary, { recursive: true, force: true }); }
