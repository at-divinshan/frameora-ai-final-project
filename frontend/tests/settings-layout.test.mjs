import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('Settings keeps privacy and security adjacent without a local theme toggle', () => {
  const source = readFileSync('src/components/common/AccountSettings.jsx', 'utf8');
  assert.ok(source.indexOf('<h2>Privacy') < source.indexOf('<h2>Account security'));
  assert.doesNotMatch(source, /<h2>Appearance|toggleTheme|account-wide/);
  assert.match(source, /Link Google account/);
});
test('Password fields retain validation and responsive containment', () => {
  const source = readFileSync('src/components/common/PasswordManagement.jsx', 'utf8');
  for (const name of ['current_password', 'new_password', 'confirm_password'])
    assert.ok(source.includes('name="' + name + '"'));
  assert.match(source, /password-management-form/);
  const css = readFileSync('src/styles/account.css', 'utf8');
  assert.match(css, /password-management-form \.form-field \{ display: grid/);
  assert.match(css, /width: 100%; min-width: 0; box-sizing: border-box/);
  assert.match(css, /max-width: 760px/);
});
