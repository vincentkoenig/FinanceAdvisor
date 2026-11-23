import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Goal } from '../../api/goals';
import { renderApp } from '../../test/renderApp';
import { data, sent, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
});

const urlaub = (changes: Partial<Goal> = {}): Goal => ({
  id: 1, name: 'Urlaub', target_amount: 3000, target_date: '2027-07-01', monthly_amount: 200, balance: 1200, missing: 1800,
  progress: 0.4, reached: false, plan: { status: 'behind', needed_monthly: 225, months_left: 8, shortfall_monthly: 25 }, ...changes,
});

const section = () => screen.findByRole('region', { name: 'Sparziele' });

describe('Sparziele im Haushaltsbuch', () => {
  it('zeigt Fortschritt und Plan', async () => {
    data.goals = { goals: [urlaub()], total: 1200, cash_balance: 2500, over_by: 0 };
    renderApp('/budget');
    const box = await section();

    expect(await within(box).findByRole('meter', { name: 'Fortschritt Urlaub' })).toHaveAttribute('aria-valuenow', '1200');
    expect(box).toHaveTextContent('1.200,00 € / 3.000,00 €');
    expect(box).toHaveTextContent('25,00 € pro Monat zu wenig für 1. Juli 2027');
  });

  it('warnt, wenn die Töpfe größer sind als das Konto', async () => {
    data.goals = { goals: [urlaub()], total: 1200, cash_balance: 900, over_by: 300 };
    renderApp('/budget');
    const box = await section();

    expect(await within(box).findByRole('alert')).toHaveTextContent('In den Töpfen liegen 300,00 € mehr, als auf dem Konto sind (900,00 €).');
  });

  it('legt ein Sparziel an und zahlt ein', async () => {
    renderApp('/budget');
    const user = userEvent.setup();
    const box = await section();
    await user.click(within(box).getByRole('button', { name: 'Sparziel' }));
    const dialog = await screen.findByRole('dialog', { name: 'Sparziel anlegen' });
    await user.type(within(dialog).getByLabelText('Name'), 'Notgroschen');
    await user.type(within(dialog).getByLabelText('Zielbetrag'), '10.000');
    await user.type(within(dialog).getByLabelText('Pro Monat (optional)'), '250');
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }));

    await waitFor(() => expect(sent.goal).toEqual({ name: 'Notgroschen', target_amount: 10000, target_date: null, monthly_amount: 250, start_amount: null }));
    expect(await within(box).findByText('Notgroschen')).toBeInTheDocument();

    await user.click(within(box).getByRole('button', { name: 'Notgroschen: einzahlen oder entnehmen' }));
    const entry = await screen.findByRole('dialog', { name: 'Notgroschen' });
    await user.type(within(entry).getByLabelText('Betrag'), '100');
    await user.click(entry.querySelector('button[type="submit"]')!);

    await waitFor(() => expect(sent.goalEntry).toEqual({ id: 90, amount: 100, note: null }));
  });

  it('lässt nicht mehr entnehmen, als im Topf ist', async () => {
    data.goals = { goals: [urlaub()], total: 1200, cash_balance: 2500, over_by: 0 };
    renderApp('/budget');
    const user = userEvent.setup();
    const box = await section();
    await user.click(await within(box).findByRole('button', { name: 'Urlaub: einzahlen oder entnehmen' }));
    const entry = await screen.findByRole('dialog', { name: 'Urlaub' });
    await user.click(within(entry).getByRole('button', { name: 'Entnehmen' }));
    await user.type(within(entry).getByLabelText('Betrag'), '1500');
    await user.click(entry.querySelector('button[type="submit"]')!);

    expect(await within(entry).findByText('Im Topf sind nur 1.200,00 €.')).toBeInTheDocument();
    expect(sent.goalEntry).toBeUndefined();
  });
});

describe('Sparziele auf der Übersicht', () => {
  it('zeigt die Töpfe nur, wenn es welche gibt', async () => {
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Gesamtvermögen' })).toBeInTheDocument();
    expect(screen.queryByText('Sparziele')).not.toBeInTheDocument();
  });

  it('zeigt Fortschritt und verlinkt zum Verwalten', async () => {
    data.goals = { goals: [urlaub({ reached: true, progress: 1, balance: 3000, missing: 0, plan: null })], total: 3000, cash_balance: 4000, over_by: 0 };
    renderApp('/');

    expect(await screen.findByRole('meter', { name: 'Fortschritt Urlaub' })).toBeInTheDocument();
    expect(screen.getByText('Ziel erreicht')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Verwalten' })).toHaveAttribute('href', '/budget#goals');
  });
});
