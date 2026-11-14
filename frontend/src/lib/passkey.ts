// Passkeys (WebAuthn) auf diesem Gerät: Anmeldung per Face ID, Touch ID oder Fingerabdruck.
// Welche Methode das Gerät nutzt, entscheidet das Gerät selbst; FinTrack merkt sich pro Gerät nur,
// ob hier ein Passkey eingerichtet ist und ob er beim Öffnen gleich angeboten werden soll.
// Das Umwandeln für navigator.credentials steht in webauthn.ts und wird erst bei Bedarf geladen.

const HAS_PASSKEY = 'fintrack-passkey';
const PREFERRED = 'fintrack-login-method';

export type LoginMethod = 'passkey' | 'password';

export function passkeySupported() {
  return typeof window !== 'undefined' && typeof window.PublicKeyCredential === 'function'
    && Boolean(navigator.credentials);
}

/** Bricht die Person die Abfrage ab (oder schließt sie), ist das kein Fehler, der angezeigt werden muss. */
export function isCancel(error: unknown) {
  return error instanceof DOMException && (error.name === 'NotAllowedError' || error.name === 'AbortError');
}

/** Wie das Gerät seine Biometrie nennt - für Knöpfe wie „Mit Face ID anmelden“. */
export function biometricName(userAgent = navigator.userAgent) {
  if (/iPhone|iPad|iPod/.test(userAgent)) return 'Face ID / Touch ID';
  if (/Macintosh/.test(userAgent)) return 'Touch ID';
  if (/Android/.test(userAgent)) return 'Fingerabdruck / Gesicht';
  if (/Windows/.test(userAgent)) return 'Windows Hello';
  return 'Passkey';
}

function read(key: string) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* privater Modus: dann eben ohne Merken */ }
}

export const devicePasskey = {
  has: () => read(HAS_PASSKEY) === '1',
  set: (has: boolean) => {
    write(HAS_PASSKEY, has ? '1' : null);
    if (!has) write(PREFERRED, null);
  },
  /** Ist hier ein Passkey eingerichtet, ist er die bevorzugte Methode, bis die Person „Passwort“ wählt. */
  preferred: (): LoginMethod => (read(HAS_PASSKEY) === '1' && read(PREFERRED) !== 'password' ? 'passkey' : 'password'),
  setPreferred: (method: LoginMethod) => write(PREFERRED, method),
};
