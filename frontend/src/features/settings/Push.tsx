// Benachrichtigungen in den Einstellungen: auf diesem Gerät ein- und ausschalten, wählen, welche
// Meldungen kommen, und eine Test-Meldung schicken. Jedes Gerät meldet sich selbst an, deshalb
// gilt alles hier nur für das Gerät, auf dem die Seite gerade offen ist.
import { useEffect, useState } from 'react';
import { pushApi, usePushConfig, type DeviceSettings } from '../../api/push';
import { ApiError } from '../../api/client';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { createSubscription, currentSubscription, PushDenied, pushSupport } from '../../lib/push';

type DeviceState =
  | { kind: 'loading' }
  | { kind: 'off' }
  | { kind: 'on'; endpoint: string; settings: DeviceSettings };

const DEFAULTS: DeviceSettings = { deadlines: true, savings_plan: true, daily_update: true, price_moves: true, watchlist: true };

const TOPICS: [keyof DeviceSettings, string, string][] = [
  ['deadlines', 'Kündigungsfristen', '14 und 3 Tage vor dem letzten Kündigungstag eines Vertrags.'],
  ['savings_plan', 'Sparplan fällig', 'Am Ausführungstag, bis du die Ausführung bestätigt hast.'],
  ['daily_update', 'Tages-Update', 'Morgens ein Hinweis, wenn der KI-Text vom Vorabend bereitliegt.'],
  ['price_moves', 'Starke Kursbewegung', 'Wenn eine Position mehr als 5 % oder das Depot mehr als 3 % vom letzten Schlusskurs abweicht. Höchstens einmal am Tag je Richtung.'],
  ['watchlist', 'Watchlist-Zielkurs', 'Wenn ein Wert auf der Watchlist deinen Zielkurs erreicht. Den Zielkurs setzt du im Portfolio unter Watchlist.'],
];

function Notice({ children }: { children: React.ReactNode }) {
  return <p className="hint">{children}</p>;
}

export function PushSection() {
  const support = pushSupport();
  const config = usePushConfig();
  const notify = useToast();
  const [device, setDevice] = useState<DeviceState>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [denied, setDenied] = useState(support === 'supported' && Notification.permission === 'denied');

  // Ist dieses Gerät schon angemeldet? Kennt der Server das Abo nicht mehr, gilt es als aus.
  useEffect(() => {
    if (support !== 'supported' || !config.data?.available) return;
    let active = true;
    (async () => {
      try {
        const subscription = await currentSubscription();
        if (!subscription) { if (active) setDevice({ kind: 'off' }); return; }
        const settings = await pushApi.settings(subscription.endpoint);
        if (active) setDevice({ kind: 'on', endpoint: subscription.endpoint, settings });
      } catch {
        if (active) setDevice({ kind: 'off' });
      }
    })();
    return () => { active = false; };
  }, [support, config.data?.available]);

  if (support === 'ios-install') {
    return <Notice>Auf dem iPhone kommen Benachrichtigungen nur in der installierten App: in Safari über Teilen → „Zum Home-Bildschirm“ installieren und FinTrack von dort öffnen.</Notice>;
  }
  if (support === 'unsupported') return <Notice>Dieser Browser unterstützt keine Push-Benachrichtigungen.</Notice>;
  if (config.isPending) return <Notice>Lädt …</Notice>;
  if (!config.data?.available) return <Notice>Push-Benachrichtigungen sind auf dem Server noch nicht eingerichtet.</Notice>;

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
    } catch (error) {
      if (error instanceof PushDenied) setDenied(true);
      else notify(error instanceof Error ? error.message : 'Das hat nicht geklappt.', { error: true });
    } finally {
      setBusy(false);
    }
  };

  const enable = () => run(async () => {
    const subscription = await createSubscription(config.data!.public_key!);
    const settings = await pushApi.subscribe(subscription.toJSON(), DEFAULTS);
    setDevice({ kind: 'on', endpoint: subscription.endpoint, settings });
    notify('Benachrichtigungen auf diesem Gerät eingeschaltet');
  });

  const disable = (endpoint: string) => run(async () => {
    const subscription = await currentSubscription();
    await subscription?.unsubscribe();
    await pushApi.remove(endpoint);
    setDevice({ kind: 'off' });
    notify('Benachrichtigungen auf diesem Gerät ausgeschaltet');
  });

  const change = (endpoint: string, key: keyof DeviceSettings, value: boolean) => run(async () => {
    const settings = await pushApi.settings(endpoint, { [key]: value });
    setDevice({ kind: 'on', endpoint, settings });
  });

  const test = (endpoint: string) => run(async () => {
    try {
      await pushApi.test(endpoint);
      notify('Test-Meldung verschickt');
    } catch (error) {
      // Kennt der Server das Gerät nicht mehr, einfach neu einschalten lassen
      if (error instanceof ApiError && error.status === 404) setDevice({ kind: 'off' });
      throw error;
    }
  });

  if (device.kind === 'loading') return <Notice>Lädt …</Notice>;

  if (device.kind === 'off') {
    return (
      <div className="switch-row">
        <div className="text">
          <span className="strong">Auf diesem Gerät</span>
          {denied
            ? <p className="hint">Benachrichtigungen sind für FinTrack blockiert. Erlaube sie in den Einstellungen des Browsers bzw. der App und versuche es dann erneut.</p>
            : <p className="hint">Meldungen kommen auch, wenn FinTrack geschlossen ist, nie zwischen 22 und 8 Uhr. Beträge stehen nie darin, weil sie auf dem Sperrbildschirm sichtbar wären.</p>}
        </div>
        <button className="btn btn-sm btn-primary" onClick={enable} disabled={busy}>
          <Icon name="bell" size={16} />{busy ? 'Schaltet ein …' : 'Einschalten'}
        </button>
      </div>
    );
  }

  return (
    <>
      {TOPICS.map(([key, label, hint]) => (
        <div className="switch-row" key={key}>
          <div className="text">
            <label htmlFor={`push-${key}`} className="strong">{label}</label>
            <p className="hint">{hint}</p>
          </div>
          <input type="checkbox" className="switch" id={`push-${key}`} checked={device.settings[key]} disabled={busy}
            onChange={(e) => change(device.endpoint, key, e.target.checked)} />
        </div>
      ))}
      <div className="switch-row">
        <div className="text">
          <span className="strong">Auf diesem Gerät eingeschaltet</span>
          <p className="hint">Jede Art lässt sich oben einzeln abschalten. Andere Geräte schaltest du dort ein.</p>
        </div>
        <button className="btn btn-sm" onClick={() => test(device.endpoint)} disabled={busy}>Test senden</button>
        <button className="btn btn-sm" onClick={() => disable(device.endpoint)} disabled={busy}>Ausschalten</button>
      </div>
    </>
  );
}
