// Anmeldung in den Einstellungen: Face ID, Touch ID oder Fingerabdruck auf diesem Gerät einrichten,
// die bevorzugte Methode für dieses Gerät wählen und eingerichtete Geräte entfernen.
// Nach 5 Minuten im Hintergrund oder geschlossen meldet FinTrack automatisch ab.
import { useState } from 'react';
import { usePasskeys, useAddPasskey, useRemovePasskey } from '../../api/passkeySettings';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { dayShort } from '../../lib/format';
import { biometricName, devicePasskey, isCancel, passkeySupported, type LoginMethod } from '../../lib/passkey';

export function PasskeySection() {
  const supported = passkeySupported();
  const passkeys = usePasskeys();
  const add = useAddPasskey();
  const remove = useRemovePasskey();
  const notify = useToast();
  const [hasHere, setHasHere] = useState(devicePasskey.has());
  const [preferred, setPreferred] = useState<LoginMethod>(devicePasskey.preferred());
  const method = biometricName();

  const setUp = () => add.mutate(undefined, {
    onSuccess: () => {
      setHasHere(true);
      setPreferred('passkey');
      notify(`${method} auf diesem Gerät eingerichtet`);
    },
    onError: (error) => {
      if (isCancel(error)) return;
      // Ist das Gerät schon eingerichtet, lehnt der Browser ab - dann einfach als eingerichtet merken
      if (error instanceof DOMException && error.name === 'InvalidStateError') {
        devicePasskey.set(true);
        setHasHere(true);
        setPreferred(devicePasskey.preferred());
        notify('Dieses Gerät ist bereits eingerichtet.');
        return;
      }
      notify(error.message, { error: true });
    },
  });

  const choose = (value: LoginMethod) => {
    devicePasskey.setPreferred(value);
    setPreferred(value);
  };

  const removeOne = (id: number, name: string) => remove.mutate(id, {
    onSuccess: () => {
      notify(`${name} entfernt`);
      // Ohne Passkeys auf dem Server kann auch dieses Gerät keinen mehr haben
      if ((passkeys.data ?? []).length <= 1) {
        devicePasskey.set(false);
        setHasHere(false);
        setPreferred('password');
      }
    },
    onError: (error) => notify(error.message, { error: true }),
  });

  return (
    <>
      <div className="switch-row">
        <div className="text">
          <span className="strong">Automatisch abmelden</span>
          <p className="hint">Liegt FinTrack 5 Minuten im Hintergrund oder ist geschlossen, meldest du dich beim nächsten Öffnen neu an.</p>
        </div>
      </div>

      {!supported ? (
        <p className="hint">Dieser Browser unterstützt keine Anmeldung per Face ID, Touch ID oder Fingerabdruck.</p>
      ) : !hasHere ? (
        <div className="switch-row">
          <div className="text">
            <span className="strong">{method} auf diesem Gerät</span>
            <p className="hint">Statt des Passworts entsperrst du FinTrack mit {method}. Gesicht und Fingerabdruck bleiben auf dem Gerät, der Server sieht sie nie.</p>
          </div>
          <button className="btn btn-sm btn-primary" onClick={setUp} disabled={add.isPending}>
            {add.isPending ? 'Richtet ein …' : 'Einrichten'}
          </button>
        </div>
      ) : (
        <div className="field">
          <span className="label" id="login-method-label">Bevorzugte Anmeldung auf diesem Gerät</span>
          <div className="segmented" role="group" aria-labelledby="login-method-label">
            <button type="button" aria-pressed={preferred === 'passkey'} onClick={() => choose('passkey')}>{method}</button>
            <button type="button" aria-pressed={preferred === 'password'} onClick={() => choose('password')}>Passwort</button>
          </div>
          <p className="hint">Mit der bevorzugten Methode beginnt die Anmeldung. Der andere Weg steht immer darunter.</p>
        </div>
      )}

      {(passkeys.data ?? []).map((passkey) => (
        <div className="switch-row" key={passkey.id}>
          <div className="text">
            <span className="strong">{passkey.name}</span>
            <p className="hint">
              {passkey.created_at ? `Eingerichtet am ${dayShort(passkey.created_at)}` : 'Eingerichtet'}
              {passkey.last_used_at ? ` · zuletzt genutzt am ${dayShort(passkey.last_used_at)}` : ''}
            </p>
          </div>
          <button className="btn btn-sm" onClick={() => removeOne(passkey.id, passkey.name)} disabled={remove.isPending}
            aria-label={`${passkey.name} entfernen`}>
            <Icon name="trash" size={16} />Entfernen
          </button>
        </div>
      ))}
    </>
  );
}
