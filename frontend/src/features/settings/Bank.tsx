// Bankabruf in den Einstellungen: Bank verbinden (Anmeldung auf der Seite der Bank über Enable Banking),
// Konten ein- und ausschalten, jetzt abrufen, Freigabe erneuern und den Zugang trennen.
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import {
  type BankConnection, useAspsps, useBank, useConnectBank, useDisconnectBank, useSyncBank, useToggleBankAccount,
} from '../../api/bank';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { dayShort } from '../../lib/format';
import './bank.css';

const PREFERRED_BANK = /hypovereinsbank|unicredit/i;
// So viele Tage vor dem Ende der Freigabe bietet FinTrack das Erneuern an
const RENEW_DAYS = 14;

const CALLBACK_MESSAGES: Record<string, { text: string; error?: boolean }> = {
  verbunden: { text: 'Bank verbunden. Der erste Abruf läuft heute Nacht, oder jetzt über „Jetzt abrufen“.' },
  abgebrochen: { text: 'Anmeldung bei der Bank abgebrochen.', error: true },
  fehler: { text: 'Die Bank konnte nicht verbunden werden. Bitte noch einmal versuchen.', error: true },
};

const daysUntil = (iso: string) => Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);

export function BankSection() {
  const bank = useBank();
  const notify = useToast();
  const [search, setSearch] = useSearchParams();
  const result = search.get('bank');

  // Rücksprung von der Bank: Ergebnis einmal melden und aus der Adresse nehmen
  useEffect(() => {
    if (!result) return;
    const message = CALLBACK_MESSAGES[result];
    if (message) notify(message.text, { error: message.error });
    setSearch({}, { replace: true });
  }, [result, notify, setSearch]);

  if (!bank.data) return null;
  const { configured, connections, redirect_url: redirectUrl, review_count: reviewCount } = bank.data;

  if (!configured) {
    return (
      <div className="bank-setup">
        <p className="hint">
          Auf dem Server fehlt noch die Einrichtung: <code>ENABLE_BANKING_APP_ID</code> und <code>ENABLE_BANKING_PRIVATE_KEY</code> aus
          deiner App bei Enable Banking.
        </p>
        <p className="hint">Rücksprung-Adresse für die App: <code className="break">{redirectUrl}</code></p>
      </div>
    );
  }

  if (bank.data.configuration_error) {
    return (
      <div className="bank-setup">
        <p className="err" role="alert">{bank.data.configuration_error}</p>
        <p className="hint">Der Schlüssel in der Einstellungsdatei des Servers lässt sich nicht lesen. Das Einrichtungs-Skript neu laufen lassen hilft meist.</p>
      </div>
    );
  }

  return (
    <>
      {reviewCount > 0 && (
        <div className="switch-row bank-review">
          <div className="text">
            <span className="strong">{reviewCount === 1 ? '1 Umsatz wartet' : `${reviewCount} Umsätze warten`} auf deine Prüfung</span>
            <p className="hint">Ohne sichere Kategorie bucht FinTrack nicht selbst.</p>
          </div>
          <Link className="btn btn-sm btn-primary" to="/budget/import?source=bank">Prüfen</Link>
        </div>
      )}
      {connections.map((connection) => <Connection key={connection.id} connection={connection} />)}
      {connections.length === 0 && <ConnectForm />}
    </>
  );
}

function Connection({ connection }: { connection: BankConnection }) {
  const sync = useSyncBank();
  const toggle = useToggleBankAccount();
  const disconnect = useDisconnectBank();
  const connect = useConnectBank();
  const notify = useToast();
  const expired = connection.status === 'expired';
  const daysLeft = connection.valid_until ? daysUntil(connection.valid_until) : null;
  const renewSoon = !expired && daysLeft !== null && daysLeft <= RENEW_DAYS;

  const syncNow = () => sync.mutate(undefined, {
    onSuccess: (r) => {
      const parts = [r.booked && `${r.booked} gebucht`, r.review && `${r.review} zur Prüfung`].filter(Boolean);
      notify(parts.length ? `Abgerufen: ${parts.join(', ')}` : 'Abgerufen, keine neuen Umsätze');
    },
    onError: (error) => notify(error.message, { error: true }),
  });
  const renew = () => connect.mutate(connection.aspsp_name, { onError: (error) => notify(error.message, { error: true }) });

  const status = expired ? 'Freigabe abgelaufen'
    : [connection.valid_until && `Freigabe bis ${dayShort(connection.valid_until)}`,
      connection.last_sync_at ? `zuletzt abgerufen ${dayShort(connection.last_sync_at)}` : 'noch nicht abgerufen'].filter(Boolean).join(' · ');

  return (
    <div className="bank-connection">
      <div className="switch-row">
        <div className="text">
          <span className="strong">{connection.aspsp_name}</span>
          <p className={`hint ${expired ? 'neg' : ''}`}>{status}</p>
          {connection.last_error && !expired && <p className="hint neg">{connection.last_error}</p>}
        </div>
        {expired || renewSoon
          ? <button className={`btn btn-sm ${expired ? 'btn-primary' : ''}`} onClick={renew} disabled={connect.isPending}>
            {connect.isPending ? 'Öffnet die Bank …' : expired ? 'Neu verbinden' : 'Erneuern'}
          </button>
          : <button className="btn btn-sm" onClick={syncNow} disabled={sync.isPending}>
            <Icon name="refresh" size={16} />{sync.isPending ? 'Ruft ab …' : 'Jetzt abrufen'}
          </button>}
      </div>
      {connection.accounts.map((account) => (
        <div className="switch-row" key={account.id}>
          <div className="text">
            <label htmlFor={`bank-account-${account.id}`} className="strong">{account.name ?? 'Konto'}{account.iban_last4 && ` ···${account.iban_last4}`}</label>
            <p className="hint">{account.enabled ? 'Umsätze und Kontostand werden abgerufen' : 'Wird nicht abgerufen'}</p>
          </div>
          <input type="checkbox" className="switch" id={`bank-account-${account.id}`} checked={account.enabled} disabled={toggle.isPending}
            onChange={(e) => toggle.mutate({ id: account.id, enabled: e.target.checked })} />
        </div>
      ))}
      <div className="bank-actions">
        {renewSoon && (
          <button className="btn btn-sm" onClick={syncNow} disabled={sync.isPending}>
            <Icon name="refresh" size={16} />{sync.isPending ? 'Ruft ab …' : 'Jetzt abrufen'}
          </button>
        )}
        <button className="btn btn-sm" onClick={() => disconnect.mutate(connection.id, {
          onSuccess: () => notify(`${connection.aspsp_name} getrennt. Gebuchte Umsätze bleiben im Haushaltsbuch.`),
          onError: (error) => notify(error.message, { error: true }),
        })} disabled={disconnect.isPending}>
          <Icon name="trash" size={16} />Trennen
        </button>
      </div>
    </div>
  );
}

function ConnectForm() {
  const aspsps = useAspsps(true);
  const connect = useConnectBank();
  const notify = useToast();
  const [chosen, setChosen] = useState<string | null>(null);
  const banks = aspsps.data ?? [];
  const selected = chosen ?? banks.find((name) => PREFERRED_BANK.test(name)) ?? banks[0] ?? '';

  if (aspsps.isError) {
    return (
      <div className="load-error" role="alert">
        <span>{aspsps.error.message}</span>
        <button className="btn btn-sm" onClick={() => aspsps.refetch()}>Erneut versuchen</button>
      </div>
    );
  }

  return (
    <div className="field">
      <label htmlFor="bank-choice">Bank</label>
      <div className="bank-connect">
        <select className="select" id="bank-choice" value={selected} onChange={(e) => setChosen(e.target.value)} disabled={!banks.length}>
          {!banks.length && <option value="">{aspsps.isPending ? 'Lädt …' : 'Keine Banken gefunden'}</option>}
          {banks.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <button className="btn btn-primary" disabled={!selected || connect.isPending}
          onClick={() => connect.mutate(selected, { onError: (error) => notify(error.message, { error: true }) })}>
          {connect.isPending ? 'Öffnet die Bank …' : 'Bei der Bank anmelden'}
        </button>
      </div>
      <p className="hint">Du meldest dich auf der Seite deiner Bank an und bestätigst den Zugriff in der Banking-App. FinTrack sieht deine Zugangsdaten nie und kann nur lesen.</p>
    </div>
  );
}
