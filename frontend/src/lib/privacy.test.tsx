import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../test/renderApp';
import { data, session } from '../test/server';
import { maskText, maskedEur } from './privacy';

beforeEach(() => {
  session.loggedIn = true;
});

describe('maskedEur', () => {
  it('ersetzt die Ziffern und lässt das Vorzeichen stehen', () => {
    expect(maskedEur(1234.5)).toBe('•••• €');
    expect(maskedEur(-20)).toBe('−•••• €');
    expect(maskedEur(20, { sign: true })).toBe('+•••• €');
    expect(maskedEur(0.001, { sign: true })).toBe('•••• €');
  });
});

describe('maskText', () => {
  it('ersetzt Euro-Beträge in freiem Text, aber keine Prozente oder Jahreszahlen', () => {
    expect(maskText('Depot bei 14.000,50 € (+1,4 %), Ziel 2027: 500 EUR im Monat, dazu € 99 und 12 Euro.'))
      .toBe('Depot bei •••• € (+1,4 %), Ziel 2027: •••• € im Monat, dazu •••• € und •••• €.');
    expect(maskText('Verlust von −250,00 € seit 2025')).toBe('Verlust von •••• € seit 2025');
  });
});

describe('Beträge verbergen', () => {
  it('verbirgt Beträge über das Auge in der Leiste und merkt sich die Wahl', async () => {
    data.insight = { content: 'Dein Depot liegt bei 14.000 € und hat 1,4 % zugelegt.', created_at: '2026-10-30 07:00' };
    renderApp('/');
    const user = userEvent.setup();
    const hero = await screen.findByRole('region', { name: 'Gesamtvermögen' });
    expect(await within(hero).findByText('16.000,00 €')).toBeInTheDocument();

    const eye = screen.getByRole('button', { name: 'Beträge verbergen' });
    await user.click(eye);
    expect(eye).toHaveAttribute('aria-pressed', 'true');
    expect(hero).not.toHaveTextContent('16.000');
    expect(hero).toHaveTextContent('Depot •••• €');
    expect(hero).toHaveTextContent('+7,7 % auf •••• € Einstand');
    expect(await screen.findByText('Dein Depot liegt bei •••• € und hat 1,4 % zugelegt.')).toBeInTheDocument();
    expect(localStorage.getItem('fintrack-hide-amounts')).toBe('1');

    await user.click(eye);
    expect(within(hero).getByText('16.000,00 €')).toBeInTheDocument();
  });

  it('lässt sich in den Einstellungen schalten', async () => {
    localStorage.setItem('fintrack-hide-amounts', '1');
    renderApp('/settings');
    const user = userEvent.setup();
    const box = await screen.findByRole('checkbox', { name: 'Beträge verbergen' });
    expect(box).toBeChecked();
    await user.click(box);
    expect(box).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Beträge verbergen' })).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem('fintrack-hide-amounts')).toBe('0');
  });
});
