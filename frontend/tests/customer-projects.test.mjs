import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';
import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';

const temporary = await mkdtemp(path.join(process.cwd(), 'tests/.projects-'));
try {
  const outfile = path.join(temporary, 'bundle.mjs');
  await build({ stdin: { contents: `export * from './src/services/projectService';
    export * from './src/services/shareService';
    export * from './src/utils/shareReturn';
    export {generateOwnerImages} from './src/services/ownerAiService';
    export {LinkedProjectPlan} from './src/components/projects/ProjectWorkspace';
    export {default as api} from './src/services/api';
    export {default as ProjectForm, projectValues} from './src/components/projects/ProjectForm';
    export {default as ProjectUsage} from './src/components/projects/ProjectUsage';`, resolveDir: process.cwd() },
    bundle: true, format: 'esm', platform: 'node', packages: 'external', loader: { '.css': 'empty' }, jsx: 'automatic', outfile,
    define: { 'import.meta.env': JSON.stringify({ VITE_API_URL: 'http://localhost:8000' }) } });
  const m = await import(pathToFileURL(outfile));
  test('customer project CRUD uses owner endpoints, PATCH and cancellable reads', async () => {
    const calls = [];
    m.api.defaults.adapter = async config => { calls.push(config); return { data: { id: 8 }, status: 200, headers: {}, config }; };
    const signal = new AbortController().signal;
    await m.getProjects(signal); await m.getProject(8, signal);
    const values = m.projectValues({ customer_name: '  Ana  ', requirements: 'line one\nline two' });
    await m.createProject(values); await m.updateProject(8, values);
    assert.deepEqual(calls.map(c => [c.method, c.url]), [['get', '/owner/projects'], ['get', '/owner/projects/8'], ['post', '/owner/projects'], ['patch', '/owner/projects/8']]);
    assert.equal(calls[0].signal, signal);
    assert.equal(JSON.parse(calls[3].data).customer_name, 'Ana');
    assert.equal(values.shooting_date, null);
    assert.equal(values.requirements, 'line one\nline two');
    assert.equal(m.projectError({ response: { status: 409, data: { detail: 'This project is read-only under your current plan.' } } }), 'This project is read-only under your current plan.');
    assert.match(m.projectError({ response: { status: 422, data: { detail: [] } } }), /Check your project details/);
  });
  test('project form preserves date-only values and disables changes at the limit', () => {
    const html = renderToStaticMarkup(React.createElement(m.ProjectForm, { project: { customer_name: 'Ana', shooting_date: '2026-11-06' }, disabled: true }));
    assert.match(html, /fieldset disabled/);
    assert.match(html, /value="2026-11-06"/);
    for (const name of ['project_title', 'customer_name', 'customer_contact', 'event_type', 'shooting_date', 'shoot_location', 'requirements']) assert.ok(html.includes(`name="${name}"`));
  });
  test('usage retains over-limit totals and distinguishes read-only projects', () => {
    const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(m.ProjectUsage, {
      projects: [{ is_editable: true }, { is_editable: false }], plan: { name: 'Basic', max_projects: 1 },
    })));
    assert.match(html, /2 projects \/ 1 limit/);
    assert.match(html, /1 editable · 1 read-only/);
    assert.match(html, /limit has been reached/);
  });

  test('project plans, images and sharing use scoped APIs without altering generation inputs', async () => {
    const calls = [];
    m.api.defaults.adapter = async config => { calls.push(config); return { data: [], status: 200, headers: {}, config }; };
    const signal = new AbortController().signal;
    const values = { photography_type: 'Portrait', people_count: 2, environment: 'Indoor' };
    await m.getProjectPlans(7, signal);
    await m.createProjectPlan(7, values);
    await m.linkProjectPlan(7, 11);
    await m.getProjectGenerations(7, signal);
    await m.getProjectShareLinks(7, signal);
    await m.createProjectShareLink(7, { generation_id: 9, expires_at: null });
    await m.deactivateProjectShareLink(7, 2);
    await m.getSharedGallery('safe_token', signal);
    await m.getSharedImage('safe_token', 19, signal);
    assert.deepEqual(calls.map(c => [c.method, c.url]), [
      ['get', '/owner/projects/7/photography-plans'], ['post', '/owner/projects/7/photography-plans'],
      ['post', '/owner/projects/7/photography-plans/11'], ['get', '/owner/projects/7/ai/generations'],
      ['get', '/owner/projects/7/share-links'], ['post', '/owner/projects/7/share-links'],
      ['delete', '/owner/projects/7/share-links/2'], ['get', '/sharing/safe_token'], ['get', '/sharing/safe_token/images/19'],
    ]);
    assert.deepEqual(JSON.parse(calls[1].data), values);
    assert.deepEqual(JSON.parse(calls[5].data), { generation_id: 9, expires_at: null });
    assert.equal(calls[8].responseType, 'blob');
    assert.equal(calls[8].signal, signal);
    await m.generateOwnerImages({ projectId: 7, planId: 11, description: 'Portrait', idempotencyKey: 'same-request-key' });
    const projectCall = calls.at(-1);
    assert.equal(projectCall.url, '/owner/projects/7/ai/generations');
    assert.equal(projectCall.data.get('plan_id'), '11');
    assert.equal(projectCall.data.get('idempotency_key'), 'same-request-key');
    assert.equal(projectCall.data.has('project_id'), false);
    await m.generateOwnerImages({ planId: 11, idempotencyKey: 'same-request-key' });
    assert.equal(calls.at(-1).url, '/owner/ai/generations');
  });
  test('share usage aggregates every project and excludes expired and inactive links', async () => {
    const future = '2099-01-01T00:00:00';
    const past = '2000-01-01T00:00:00';
    assert.equal(m.shareLinkStatus({ is_active: true, expires_at: past }), 'Expired');
    assert.equal(m.shareLinkStatus({ is_active: false, expires_at: future }), 'Inactive');
    m.api.defaults.adapter = async config => ({ data: config.url === '/owner/projects' ? [{ id: 1 }, { id: 2 }] :
      config.url.includes('/1/') ? [{ is_active: true, expires_at: future }, { is_active: true, expires_at: past }] :
      [{ is_active: true, expires_at: null }, { is_active: false, expires_at: null }], status: 200, headers: {}, config });
    assert.equal(await m.getShareUsage(), 2);
    for (const status of [404, 410]) assert.match(m.sharingError({ response: { status } }), /invalid, expired, or deactivated/);
  });
  test('gallery return destinations reject external URLs and unrelated internal routes', () => {
    assert.equal(m.shareReturnFromSearch('?returnTo=%2Fsharing%2Fvalid-token_1'), '/sharing/valid-token_1');
    for (const value of ['https://evil.example', '//evil.example', '/owner/dashboard', '/sharing/a/../b', '/sharing/a?next=evil', '/sharing/a\\evil']) {
      assert.equal(m.safeShareReturn(value), null);
    }
  });
  test('linked plans remain viewable after downgrade without a generation action', () => {
    const plan = { id: 4, project_id: 7, photography_type: 'Portrait', environment: 'Indoor', people_count: 2, location: 'Studio', preferences: { clothing_style: 'Formal' } };
    const render = editable => renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(m.LinkedProjectPlan, { plan, editable, projectId: 7 })));
    const locked = render(false);
    assert.match(locked, /Open plan #4/);
    assert.match(locked, /Formal/);
    assert.ok(!locked.includes('Generate 2 images'));
    assert.match(render(true), /Generate 2 images \/ 2 credits/);
    assert.match(render(true), /project=7&amp;plan=4/);
    assert.deepEqual(m.eligibleProjectPlans([plan, { id: 5, project_id: null }]), [{ id: 5, project_id: null }]);
  });
} finally { await rm(temporary, { recursive: true, force: true }); }
