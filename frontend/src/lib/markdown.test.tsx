import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Markdown, parseBlocks } from './markdown';

describe('Markdown', () => {
  it('erkennt Absätze, Überschriften, Listen und Tabellen', () => {
    expect(parseBlocks('## Kurz gesagt\nErste Zeile\nzweite Zeile\n\n- a\n- b\n\n1. eins\n2. zwei\n\n| Titel | Wert |\n|---|---:|\n| ETF | 10 € |')).toEqual([
      { kind: 'h', text: 'Kurz gesagt' },
      { kind: 'p', text: 'Erste Zeile zweite Zeile' },
      { kind: 'ul', items: ['a', 'b'] },
      { kind: 'ol', items: ['eins', 'zwei'] },
      { kind: 'table', head: ['Titel', 'Wert'], rows: [['ETF', '10 €']] },
    ]);
  });

  it('setzt fett, kursiv, Code und Links als Elemente, nie als HTML', () => {
    const { container } = render(<Markdown text={'**Fett** und *kursiv* mit `Code`, [Quelle](https://example.org) und <img src=x onerror=alert(1)>'} />);
    const p = container.querySelector('p')!;
    expect(p.querySelector('strong')).toHaveTextContent('Fett');
    expect(p.querySelector('em')).toHaveTextContent('kursiv');
    expect(p.querySelector('code')).toHaveTextContent('Code');
    expect(p.querySelector('a')).toHaveAttribute('href', 'https://example.org');
    expect(p.querySelector('a')).toHaveAttribute('rel', 'noopener noreferrer');
    // Markup aus der Antwort bleibt Text
    expect(container.querySelector('img')).toBeNull();
    expect(p).toHaveTextContent('<img src=x onerror=alert(1)>');
  });

  it('macht aus Links ohne http(s) nur Text', () => {
    const { container } = render(<Markdown text="[klick](javascript:alert(1))" />);
    expect(container.querySelector('a')).toBeNull();
    expect(container).toHaveTextContent('klick');
  });
});
