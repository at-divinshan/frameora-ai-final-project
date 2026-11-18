import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useAuth from '../../hooks/useAuth';
import api from '../../services/api';
import { clearGoogleFlow, startGoogle } from '../../services/googleAuthService';
import Button from './Button';

export default function PasswordManagement({ setup = false, verify = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (pending.current) return;
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (!verify && (values.new_password.length < 8 || !/[A-Z]/.test(values.new_password) || !/[a-z]/.test(values.new_password) || values.new_password !== values.confirm_password)) {
      setError('Use at least 8 characters with uppercase and lowercase letters, and matching passwords.'); return;
    }
    pending.current = true; setBusy(true); setError('');
    try {
      if (verify) { await startGoogle({ setup: true, userId: user.id }); return; }
      const { data } = await api.post(setup ? '/auth/google/password-setup/complete' : '/auth/password/change', values, { withCredentials: setup });
      if (data.status !== 'password_updated' || data.reauthentication_required !== true) throw new Error();
      clearGoogleFlow(); await logout();
      navigate('/login', { replace: true, state: { message: 'Password updated. Please sign in again.' } });
    } catch (failure) {
      setError(failure.response?.status === 429 ? 'Too many attempts. Please wait before trying again.' : setup ? 'Password setup could not be completed. Restart Google verification from Settings.' : typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Password change could not be confirmed. Try signing in before retrying.');
    } finally { pending.current = false; setBusy(false); }
  }
  return <form className="password-management-form" onSubmit={submit}>
    {verify ? <p>Verify your Google account before setting a password.</p> : <>
      {!setup && <label className="form-field">Current password<input className="form-input" name="current_password" type="password" autoComplete="current-password" required maxLength={128} disabled={busy}/></label>}
      <label className="form-field">New password<input className="form-input" name="new_password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} disabled={busy}/></label>
      <label className="form-field">Confirm password<input className="form-input" name="confirm_password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} disabled={busy}/></label>
      <p>Use at least 8 characters with uppercase and lowercase letters. All existing sessions will be invalidated.</p>
    </>}
    {error && <p role="alert">{error}</p>}
    <Button type="submit" loading={busy}>{verify ? 'Verify with Google and set password' : setup ? 'Set password' : 'Change password'}</Button>
  </form>;
}
