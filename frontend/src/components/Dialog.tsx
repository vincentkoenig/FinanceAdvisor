// Dialog wie im Prototyp: Kopf mit optionalem Zeichen, Titel und Schließen-Knopf. Am Laptop mittig,
// auf dem Handy als Blatt von unten. Esc und ein Klick daneben schließen ihn, solange nichts gespeichert wird.
import { useEffect, useRef, type ReactNode } from 'react';
import { Icon } from './Icon';

type Props = {
  title: string;
  onClose: () => void;
  busy?: boolean;
  lead?: ReactNode;
  children: ReactNode;
};

export function Dialog({ title, onClose, busy = false, lead, children }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = busy ? () => {} : onClose;
  });

  useEffect(() => {
    // Fokus ins erste Feld, beim Schließen zurück dorthin, wo er vorher war
    const before = document.activeElement as HTMLElement | null;
    box.current?.querySelector<HTMLElement>('input, select, textarea, [data-autofocus]')?.focus();
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && close.current();
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      before?.focus?.();
    };
  }, []);

  return (
    <div className="overlay overlay-center dialog-overlay" onClick={(e) => e.target === e.currentTarget && close.current()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title" ref={box}>
        <div className="dialog-head">
          {lead}
          <h2 id="dialog-title">{title}</h2>
          <button className="icon-btn" onClick={() => close.current()} aria-label="Schließen" disabled={busy}><Icon name="close" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
