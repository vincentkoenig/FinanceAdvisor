// Anmeldung mit E-Mail und Passwort. Fehlermeldungen kommen auf Deutsch von der API.
import { useEffect, useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router';
import { useLogin, useMe } from '../../api/auth';
import { Mark } from '../../components/Icon';

export function LoginPage() {
  const { data: user } = useMe();
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    document.title = 'Anmelden · FinTrack';
  }, []);

  if (user) return <Navigate to={from} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim() || !password) { setMissing(true); return; }
    setMissing(false);
    login.mutate({ email: email.trim(), password }, { onSuccess: () => navigate(from, { replace: true }) });
  };

  const error = missing ? 'Bitte E-Mail und Passwort eingeben.' : login.error?.message;

  return (
    <main className="login">
      <form className="login-box" onSubmit={submit} noValidate>
        <div className="mark"><Mark /><span>FinTrack</span></div>
        <h1>Anmelden</h1>
        <div className="field">
          <label htmlFor="email">E-Mail</label>
          <input className="input" id="email" type="email" autoComplete="email" value={email}
            onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? 'login-error' : undefined} />
        </div>
        <div className="field">
          <label htmlFor="password">Passwort</label>
          <input className="input" id="password" type="password" autoComplete="current-password" value={password}
            onChange={(event) => setPassword(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? 'login-error' : undefined} />
        </div>
        {error && <p className="err" id="login-error" role="alert">{error}</p>}
        <button className="btn btn-primary btn-block" type="submit" style={{ height: 40 }} disabled={login.isPending}>
          {login.isPending ? 'Melde an …' : 'Anmelden'}
        </button>
        <p className="hint">Konten legt der Betreiber an. Passwort vergessen? Melde dich beim Betreiber.</p>
      </form>
    </main>
  );
}
