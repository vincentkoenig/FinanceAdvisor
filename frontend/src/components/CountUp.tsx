// Die große Zahl einer Leitkarte zählt beim ersten Erscheinen kurz hoch (und bei späteren Änderungen
// vom alten zum neuen Wert). Im DOM-Text steht nur der Endwert (Screenreader, Kopieren, Tests); die
// laufende Zahl zeigt CSS aus data-value. Bei "Bewegung reduzieren" steht der Endwert sofort da.
import { useEffect, useRef, useState } from 'react';

const DURATION = 600;

function animate() {
  return typeof requestAnimationFrame !== 'undefined' && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

export function CountUp({ value, format }: { value: number; format: (value: number) => string }) {
  const [moving] = useState(animate);
  const [shown, setShown] = useState(moving ? 0 : value);
  const from = useRef(shown);

  useEffect(() => {
    if (!moving) return;
    const start = from.current;
    const began = performance.now();
    let frame = requestAnimationFrame(function step() {
      const t = Math.min(1, (performance.now() - began) / DURATION);
      const current = t < 1 ? start + (value - start) * (1 - (1 - t) ** 3) : value;
      from.current = current;
      setShown(current);
      if (t < 1) frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [moving, value]);

  const done = !moving || shown === value;
  return done
    ? <>{format(value)}</>
    : <span className="count-up" data-value={format(shown)}><span className="sr-only">{format(value)}</span></span>;
}
