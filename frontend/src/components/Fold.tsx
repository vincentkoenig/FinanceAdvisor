// Ein Bereich, der auf dem Handy eingeklappt startet und im Kopf seinen wichtigsten Wert zeigt.
// Auf größeren Bildschirmen ist er eine normale Fläche.
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
  // Am Laptop eine normale Fläche; nur auf dem Handy aufklappbar. Der Zusatz (Link) steht nie in der
  // Zusammenfassung, denn ein Link in einem Klappknopf ist für Screenreader nicht bedienbar.
  if (!phone) {
    return (
      <section className={`panel ${className}`} aria-labelledby={id}>
        <div className="panel-head"><h2 id={id}>{title}</h2>{action}</div>
        {children}
      </section>
    );
  }
  return (
    <details className={`panel fold ${className}`} aria-labelledby={id}>
      <summary>
        <div className="panel-head"><h2 id={id}>{title}</h2></div>
        <span className="fold-peek">{peek}</span>
        <span className="fold-chev"><Icon name="down" size={16} /></span>
      </summary>
      {children}
    </details>
  );
}
