// Isolated routing checks: no network or database access.
import { build } from 'esbuild';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
import test from 'node:test';
import { onboardingDestination } from '../src/utils/onboarding.js';

const directory = await mkdtemp(path.join(process.cwd(), 'tests/.share-routing-'));
try {
  const outfile = path.join(directory, 'checks.mjs');
  await build({ stdin: { resolveDir: process.cwd(), contents: `
    import React from 'react';
    import { renderToStaticMarkup } from 'react-dom/server';
    import { MemoryRouter, Routes, Route } from 'react-router-dom';
    import { AuthContext } from './src/context/AuthContext';
    import { ThemeProvider } from './src/context/ThemeContext';
    import ProtectedRoute from './src/routes/ProtectedRoute';
    import RoleRoute from './src/routes/RoleRoute';
    import OwnerLayout from './src/components/layout/OwnerLayout';
    export function access(user, loading = false) {
      return renderToStaticMarkup(<AuthContext.Provider value={{user, loading}}>
        <MemoryRouter initialEntries={['/owner/share-links']}><Routes>
          <Route element={<ProtectedRoute />}><Route element={<RoleRoute role="owner" />}>
            <Route path="/owner/share-links" element={<span>authorized-share-page</span>} />
          </Route></Route>
        </Routes></MemoryRouter>
      </AuthContext.Provider>);
    }
    export function sidebar() {
      return renderToStaticMarkup(<AuthContext.Provider value={{user:{id:1,role:'owner',name:'Owner'}}}>
        <ThemeProvider><MemoryRouter initialEntries={['/owner/share-links']}><OwnerLayout /></MemoryRouter></ThemeProvider>
      </AuthContext.Provider>);
    }
  `, loader: 'jsx' }, bundle: true, format: 'esm', platform: 'node', packages: 'external',
    jsx: 'automatic', loader: { '.css': 'empty' }, outfile, define: { 'import.meta.env': '{}' } });
  const checks = await import(pathToFileURL(outfile));
  test('completed Owner can pass the Share Links onboarding guard', () => {
    assert.equal(onboardingDestination('completed', '/owner/share-links'), null);
  });
  test('Share Links preserves incomplete onboarding restrictions', () => {
    assert.equal(onboardingDestination('pending_studio', '/owner/share-links'), '/owner/studio-setup');
    assert.equal(onboardingDestination('pending_plan', '/owner/share-links'), '/owner/subscription');
    assert.throws(() => onboardingDestination('unknown', '/owner/share-links'));
  });
  test('direct Share Links route permits only authenticated Owners', () => {
    assert.match(checks.access({id:1, role:'owner'}), /authorized-share-page/);
    for (const user of [null, {role:'user'}, {role:'admin'}]) {
      assert.doesNotMatch(checks.access(user), /authorized-share-page/);
    }
    assert.doesNotMatch(checks.access({role:'owner'}, true), /authorized-share-page/);
  });
  test('Owner sidebar targets the registered Share Links route', async () => {
    assert.match(checks.sidebar(), /href="\/owner\/share-links"/);
    const routes = await readFile('src/routes/AppRoutes.jsx', 'utf8');
    assert.match(routes, /import SharedLinks from "\.\.\/pages\/owner\/SharedLinks"/);
    assert.match(routes, /path="\/owner\/share-links" element=\{<SharedLinks\s*\/>\}/);
  });
} finally {
  await rm(directory, { recursive: true, force: true });
}
