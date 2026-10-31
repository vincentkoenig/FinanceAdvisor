import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { eur } from '../lib/format';
import { CountUp } from './CountUp';
import { Skeleton } from './Loaded';

afterEach(() => vi.restoreAllMocks());

function reduceMotion(reduce: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    matches: reduce && query.includes('reduce'), media: query, onchange: null,
    addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  }));
}

describe('CountUp', () => {
  it('zählt hoch, im Text steht dabei immer der Endwert', async () => {
    reduceMotion(false);
    const { container } = render(<p><CountUp value={1234.5} format={eur} /></p>);
    expect(screen.getByText('1.234,50 €')).toBeInTheDocument();
    expect(container.querySelector('.count-up')).not.toBeNull();
    await waitFor(() => expect(container.querySelector('.count-up')).toBeNull());
    expect(container.querySelector('p')).toHaveTextContent(/^1\.234,50 €$/);
  });

  it('zeigt bei "Bewegung reduzieren" sofort den Endwert', () => {
    reduceMotion(true);
    const { container } = render(<p><CountUp value={99} format={eur} /></p>);
    expect(container.querySelector('.count-up')).toBeNull();
    expect(container.querySelector('p')).toHaveTextContent(/^99,00 €$/);
  });
});

describe('Skeleton', () => {
  it('meldet das Laden ohne sichtbaren Text', () => {
    render(<Skeleton shape="figure" />);
    expect(screen.getByRole('status', { name: 'Lädt' })).toHaveTextContent(/^$/);
  });
});
