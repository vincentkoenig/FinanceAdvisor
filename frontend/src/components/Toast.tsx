// Kurze Rückmeldungen unten in der Mitte ("Gespeichert"), verschwinden nach gut zwei Sekunden.
// Fehler bleiben etwas länger stehen und werden von Screenreadern sofort vorgelesen.
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

type Toast = { id: number; text: string; error: boolean };
type Notify = (text: string, options?: { error?: boolean }) => void;

const ToastContext = createContext<Notify>(() => {});

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback<Notify>((text, { error = false } = {}) => {
    const id = nextId++;
    setToasts((list) => [...list, { id, text, error }]);
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), error ? 5000 : 2600);
  }, []);

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast${t.error ? ' toast-error' : ''}`} role={t.error ? 'alert' : 'status'}>{t.text}</div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
