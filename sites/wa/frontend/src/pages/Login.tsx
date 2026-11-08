import { useState, type FormEvent } from 'react';
import { useAuth } from '../components/auth';
import { csrfToken } from '../lib/api';

export default function Login() {
  const { login, register, signupEnabled, marketian } = useAuth();
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  // With the Marketian account, the username form is only for team members and the admin.
  const [showPasswordForm, setShowPasswordForm] = useState(!marketian.enabled);
  const [username, setUsername] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const signup = mode === 'signup' && signupEnabled;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (signup && password !== password2) return setError('The two passwords are different.');
    setBusy(true);
    try {
      if (signup) await register({ username: username.trim(), name: name.trim(), password });
      else await login(username.trim(), password);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function switchTo(m: 'signin' | 'signup') {
    setMode(m);
    setError('');
    setPassword('');
    setPassword2('');
  }

  return (
    <div className="center-screen">
      <div className="panel login">
        <div className="brand"><span className="logo" aria-hidden="true" /><span>WA Broadcaster</span></div>
        <h1>{signup ? 'Create an account' : 'Sign in'}</h1>

        {marketian.enabled && (
          // A real form post: the server sends the browser on to accounts.marketian.net and back.
          <form method="post" action={marketian.login_url} className="stack" onSubmit={e => {
            (e.currentTarget.elements.namedItem('csrfmiddlewaretoken') as HTMLInputElement).value = csrfToken();
          }}>
            <input type="hidden" name="csrfmiddlewaretoken" />
            <button className="primary" type="submit">Continue with Marketian account</button>
            <p className="small" style={{ margin: 0, textAlign: 'center' }}>
              GitHub or email. New here? You can create a Marketian account on the next screen.
            </p>
          </form>
        )}

        {marketian.enabled && !showPasswordForm && (
          <p className="small" style={{ margin: 0, textAlign: 'center' }}>
            Team member or admin? <button type="button" className="linklike" onClick={() => setShowPasswordForm(true)}>Sign in with a username</button>
          </p>
        )}

        {showPasswordForm && (
          <form className="stack" onSubmit={submit}>
            {signup && <p className="small" style={{ margin: 0 }}>You get your own workspace: your own WhatsApp accounts, contacts and campaigns. Nobody else can see them.</p>}
            {marketian.enabled && <p className="small" style={{ margin: 0 }}>For team members and the admin: use the username and password you were given.</p>}
            <label className="field">
              <span>Username</span>
              <input type="text" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required autoFocus maxLength={150} />
            </label>
            {signup && (
              <label className="field">
                <span>Your name or business (optional)</span>
                <input type="text" autoComplete="name" value={name} onChange={e => setName(e.target.value)} maxLength={150} />
              </label>
            )}
            <label className="field">
              <span>{signup ? 'Password (10+ characters)' : 'Password'}</span>
              <input type="password" autoComplete={signup ? 'new-password' : 'current-password'} value={password}
                onChange={e => setPassword(e.target.value)} required minLength={signup ? 10 : undefined} />
            </label>
            {signup && (
              <label className="field">
                <span>Password again</span>
                <input type="password" autoComplete="new-password" value={password2} onChange={e => setPassword2(e.target.value)} required />
              </label>
            )}
            <p className="err" role="alert">{error}</p>
            <button className={marketian.enabled ? '' : 'primary'} type="submit" disabled={busy}>
              {busy ? (signup ? 'Creating…' : 'Signing in…') : signup ? 'Create account' : 'Sign in'}
            </button>
            {signupEnabled && (
              <p className="small" style={{ margin: 0, textAlign: 'center' }}>
                {signup
                  ? <>Already have an account? <button type="button" className="linklike" onClick={() => switchTo('signin')}>Sign in</button></>
                  : <>New here? <button type="button" className="linklike" onClick={() => switchTo('signup')}>Create an account</button></>}
              </p>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
