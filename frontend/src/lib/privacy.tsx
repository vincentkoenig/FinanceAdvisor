// "Beträge verbergen": Euro-Beträge und Stückzahlen werden zu Punkten, z. B. für die App unterwegs.
// Pro Gerät gespeichert. Prozente bleiben sichtbar; in KI-Texten werden Euro-Beträge ersetzt.
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { eur, qty } from './format';

const KEY = 'fintrack-hide-amounts';
const MINUS = '−';
export const MASK = '••••';

type Privacy = { hidden: boolean; setHidden: (hidden: boolean) => void };
const PrivacyContext = createContext<Privacy>({ hidden: false, setHidden: () => {} });

function initialHidden() {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [hidden, setState] = useState(initialHidden);

  const setHidden = useCallback((next: boolean) => {
    setState(next);
    try {
      localStorage.setItem(KEY, next ? '1' : '0');
    } catch {
      // nicht speicherbar, gilt dann nur bis zum Neuladen
    }
  }, []);

  const value = useMemo(() => ({ hidden, setHidden }), [hidden, setHidden]);
  return <PrivacyContext.Provider value={value}>{children}</PrivacyContext.Provider>;
}

export function usePrivacy() {
  return useContext(PrivacyContext);
}

/** Vorzeichen bleibt sichtbar, damit Gewinn und Verlust lesbar bleiben: "+•••• €" */
export function maskedEur(value: number, { sign = false, digits = 2 }: { sign?: boolean; digits?: number } = {}) {
  const rounded = Number(value.toFixed(digits));
  const prefix = rounded < 0 ? MINUS : sign && rounded > 0 ? '+' : '';
  return `${prefix}${MASK} €`;
}

// "1.234,56 €", "−250 EUR", "12 Euro", "€ 99": Zahl mit Währung davor oder danach. Innerhalb der Zahl
// keine Leerzeichen, damit "2025 1.000 €" nicht die Jahreszahl mitnimmt.
const AMOUNT = /[+\-−]?\d(?:[\d.,]*\d)?\s?(?:€|EUR\b|Euro\b)|€\s?\d(?:[\d.,]*\d)?/g;

/** Euro-Beträge in freiem Text (KI-Antworten) durch Punkte ersetzen */
export function maskText(text: string) {
  return text.replace(AMOUNT, `${MASK} €`);
}

const plain = { eur, qty, text: (value: string) => value };
const masked = { eur: maskedEur, qty: () => MASK, text: maskText };

/** eur() und qty() wie in lib/format, text() für freien Text; bei verborgenen Beträgen als Punkte */
export function useMoney() {
  return usePrivacy().hidden ? masked : plain;
}
