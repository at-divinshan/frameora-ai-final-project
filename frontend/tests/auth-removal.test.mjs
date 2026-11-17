import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, access } from 'node:fs/promises';
test('removed authentication features have no frontend entry points', async () => {
  for (const name of ['routes/AppRoutes.jsx','components/auth/LoginForm.jsx','services/authService.js']) {
    const text = await readFile(new URL('../src/'+name, import.meta.url), 'utf8');
    assert.doesNotMatch(text, /ForgotPassword|forgot-password|reset-password|requestPasswordReset|change-email/);
  }
  await assert.rejects(access(new URL('../src/pages/auth/ForgotPassword.jsx', import.meta.url)));
  const settings = await readFile(new URL('../src/components/common/AccountSettings.jsx', import.meta.url),'utf8');
  assert.match(settings,/Change password/);
  assert.match(settings,/Link Google account/);
});
