import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import Login from './Login';
import Button from '../../components/common/Button';
import api from '../../services/api';

export default function EmailVerification() {
  const location = useLocation();
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '');
  const [available, setAvailable] = useState(false);
  const [deliveryAvailable, setDeliveryAvailable] = useState(false);
  const [message, setMessage] = useState('Checking verification availability…');
  const [email, setEmail] = useState(location.state?.email || '');
  const [busy, setBusy] = useState(false);
  const [verified, setVerified] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const locked = useRef(false);
  useEffect(() => {
    window.history.replaceState(window.history.state, '', window.location.pathname);
    const controller = new AbortController();
    api.get('/auth/email-verification/readiness', { signal: controller.signal }).then(({data}) => {
      setAvailable(data.available === true);
      setDeliveryAvailable(data.delivery_available === true);
      setMessage(data.available ? token ? 'Confirm your email address below.' : location.state?.emailSent === false ? 'Your account was created, but the email could not be sent. Request another link below.' : 'Check your email for a verification link. Links expire after 30 minutes.' : 'Email verification is temporarily unavailable. Please try again later.');
    }).catch(() => { if (!controller.signal.aborted) setMessage('Verification is temporarily unavailable. Please try again later.'); });
    return () => controller.abort();
  }, [token]);
  useEffect(() => {
    if (!cooldown) return;
    const timer = setTimeout(() => setCooldown(value => Math.max(0, value - 1)), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);
  async function submit(event, resend) {
    event.preventDefault();
    if (locked.current || !available || (resend && (cooldown || !deliveryAvailable))) return;
    locked.current = true; setBusy(true);
    try {
      const { data } = await api.post('/auth/email-verification/' + (resend ? 'resend' : 'verify'), resend ? { email } : { token });
      if (!resend && data.status !== 'verified') throw new Error();
      setMessage(resend ? 'If this account needs verification, an email will be sent.' : 'Email verified. You can now sign in.');
      if (resend) setCooldown(60); else setVerified(true);
    } catch (failure) {
      setMessage([400, 422].includes(failure.response?.status) ? 'This link is invalid, expired or already used. Request another link below.' : failure.response?.status === 429 ? 'Please wait before requesting another email.' : 'Verification could not be completed. Please try again later.');
      if (resend) setCooldown(60);
    } finally { locked.current = false; setBusy(false); }
  }
  return <Login>
    <div className="form-heading"><h1>{verified ? 'Email verified' : token ? 'Verify your email' : 'Check your email'}</h1></div>
    <p role="status">{message}</p>
    {available && !verified && <>
      {token && <form onSubmit={event => submit(event, false)}><Button type="submit" loading={busy}>Verify email</Button></form>}
      {!deliveryAvailable && <p role="status">Sending verification emails is temporarily unavailable. Existing links can still be verified.</p>}
      <form onSubmit={event => submit(event, true)}>
        <label className="form-field">Email address<input className="form-input" type="email" autoComplete="email" required maxLength={255} value={email} onChange={event => setEmail(event.target.value)} disabled={busy}/></label>
        <Button type="submit" disabled={busy || cooldown > 0 || !deliveryAvailable}>{cooldown ? `Resend in ${cooldown}s` : 'Resend verification email'}</Button>
      </form>
    </>}
    <p className="auth-switch"><Link to="/login">Back to login</Link></p>
  </Login>;
}
