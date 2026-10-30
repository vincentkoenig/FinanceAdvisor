// Ein Bereich, der auf dem Handy eingeklappt startet und im Kopf seinen wichtigsten Wert zeigt.
// Auf größeren Bildschirmen ist er immer offen und sieht aus wie eine normale Fläche.
import { useSyncExternalStore, type ReactNode } from 'react';
import { Icon } from './Icon';

const PHONE = '(max-width: 767px)';

function subscribe(onChange: () => void) {
  const query = window.matchMedia(PHONE);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

export function useIsPhone() {
  return useSyncExternalStore(subscribe, () => window.matchMedia(PHONE).matches, () => false);
}

type Props = {
  id: string;
  title: string;
  /** Wert, der im eingeklappten Zustand neben dem Titel steht */
  peek: ReactNode;
  /** Zusatz im Kopf, z. B. ein Link (auf dem Handy im Kopf ausgeblendet) */
  action?: ReactNode;
  className?: string;
  children: ReactNode;
};

export function Fold({ id, title, peek, action, className = '', children }: Props) {
  const phone = useIsPhone();
  return (
    // key: beim Wechsel zwischen Handy und Laptop neu aufbauen, damit "open" wieder stimmt
    <details key={String(phone)} className={`panel fold ${className}`} open={!phone} aria-labelledby={id}>
      <summary>
        <div className="panel-head"><h2 id={id}>{title}</h2>{action}</div>
        <span className="fold-peek">{peek}</span>
        <span className="fold-chev"><Icon name="down" size={16} /></span>
      </summary>
      {children}
    </details>
  );
}
