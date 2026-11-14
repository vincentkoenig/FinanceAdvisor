// Anmeldung mit Passkey (Face ID, Touch ID, Fingerabdruck) oder E-Mail und Passwort.
// Ist auf diesem Gerät ein Passkey eingerichtet und bevorzugt, startet die Abfrage beim Öffnen von selbst;
// das Passwort bleibt immer als zweiter Weg. Fehlermeldungen kommen auf Deutsch von der API.
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router';
import { useLogin, useMe } from '../../api/auth';
import { usePasskeyLogin } from '../../api/passkeys';
import { Mark } from '../../components/Icon';
import { biometricName, devicePasskey, isCancel, passkeySupported } from '../../lib/passkey';

export function LoginPage() {
  const { data: user } = useMe();
  const login = useLogin();
  const passkey = usePasskeyLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/';
  const supported = passkeySupported();
  const preferPasskey = supported && devicePasskey.preferred() === 'passkey';
  const [showPassword, setShowPassword] = useState(!preferPasskey);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [missing, setMissing] = useState(false);
  const autoStarted = useRef(false);

  useEffect(() => {
    document.title = 'Anmelden · FinTrack';
  }, []);

  const startPasskey = () => passkey.mutate(undefined, { onSuccess: () => navigate(from, { replace: true }) });

  // Bevorzugte Methode gleich anbieten - einmal pro Öffnen. Lehnt der Browser das ohne Tippen ab
  // (manche verlangen einen Klick), bleibt der Knopf dafür stehen.
  useEffect(() => {
    if (!preferPasskey || user || autoStarted.current) return;
    autoStarted.current = true;
    startPasskey();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferPasskey, user]);

  if (user) return <Navigate to={from} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim() || !password) { setMissing(true); return; }
    setMissing(false);
    login.mutate({ email: email.trim(), password }, { onSuccess: () => navigate(from, { replace: true }) });
  };

  const error = missing ? 'Bitte E-Mail und Passwort eingeben.' : login.error?.message;
  const passkeyError = passkey.error && !isCancel(passkey.error) ? passkey.error.message : null;
  const passkeyButton = (
    <button className={`btn btn-block ${showPassword ? '' : 'btn-primary'}`} type="button" style={{ height: 40 }}
      onClick={startPasskey} disabled={passkey.isPending}>
      {passkey.isPending ? 'Warte auf Bestätigung …' : `Mit ${biometricName()} anmelden`}
    </button>
  );

  return (
    <main className="login">
      <form className="login-box" onSubmit={submit} noValidate>
        <div className="mark"><Mark /><span>FinTrack</span></div>
        <h1>Anmelden</h1>
        {!showPassword ? (
          <>
            {passkeyButton}
            {passkeyError && <p className="err" role="alert">{passkeyError}</p>}
            <button className="btn btn-text btn-block" type="button" onClick={() => setShowPassword(true)}>
              Stattdessen mit Passwort anmelden
            </button>
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor="email">E-Mail</label>
              <input className="input" id="email" type="email" autoComplete="email webauthn" value={email}
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
            {supported && devicePasskey.has() && (
              <>
                {passkeyButton}
                {passkeyError && <p className="err" role="alert">{passkeyError}</p>}
              </>
            )}
          </>
        )}
        <p className="hint">Konten legt der Betreiber an. Passwort vergessen? Melde dich beim Betreiber.</p>
      </form>
    </main>
  );
}
