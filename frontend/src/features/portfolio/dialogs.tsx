// Dialoge des Portfolios: Asset hinzufügen oder beobachten, Kauf und Verkauf einer Position,
// Kauf aus der Watchlist, Sparplan anlegen und löschen.
import { useState, type FormEvent } from 'react';
import {
  type SearchResult, type WatchItem, ensureAsset, useAsset, useAssetSearch, useBuy, useCreatePlan, useDeletePlan, useSell, useUnwatch, useWatch,
} from '../../api/portfolio';
import type { SavingsPlan } from '../../api/overview';
import { Dialog } from '../../components/Dialog';
import { Actions, type Errors, Field, apiErrors, describe, positive } from '../../components/form';
import { useToast } from '../../components/Toast';
import { isoDay, pct, tone } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import { type PositionRow, token } from '../home/model';

const TYPE_NAMES: Record<string, string> = { etf: 'ETF', stock: 'Aktie', crypto: 'Krypto', metal: 'Edelmetall' };

// Betrag für ein Eingabefeld: 129.96 → "129,96"
const fieldAmount = (value: number | null | undefined) =>
  value ? value.toLocaleString('de-DE', { maximumFractionDigits: 6, useGrouping: false }) : '';

// ─── Asset suchen und hinzufügen ───

export function AddAssetDialog({ mode, onClose }: { mode: 'buy' | 'watch'; onClose: () => void }) {
  const { qty } = useMoney();
  const [query, setQuery] = useState('');
  const [picked, setPicked] = useState<SearchResult | null>(null);
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState<string | null>(null);
  const [date, setDate] = useState(isoDay(new Date()));
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);
  const search = useAssetSearch(query);
  const known = useAsset(picked?.asset_id ?? null);
  const buy = useBuy();
  const watch = useWatch();
  const notify = useToast();
  const watching = mode === 'watch';
  // Bekannte Assets haben einen Kurs; der dient als Vorschlag, bis selbst etwas eingetragen wird
  const priceText = price ?? fieldAmount(known.data?.current_price);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!picked) return;
    const found: Errors = {};
    const amount = watching ? 0 : positive(quantity, 'eine Stückzahl', found, 'quantity');
    const unitPrice = watching ? 0 : positive(priceText, 'einen Kaufpreis', found, 'price');
    if (!watching && !date) found.date = 'Bitte ein Kaufdatum wählen.';
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const assetId = await ensureAsset(picked);
      if (watching) {
        await watch.mutateAsync(assetId);
        notify(`${picked.name} steht jetzt auf der Watchlist`);
      } else {
        await buy.mutateAsync({ asset_id: assetId, quantity: amount, avg_buy_price: unitPrice, bought_at: date });
        notify(`Gekauft: ${qty(amount)} × ${picked.name}`);
      }
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { quantity: 'quantity', avg_buy_price: 'price', bought_at: 'date', symbol: 'form' }));
      setBusy(false);
    }
  };

  const results = query.trim().length >= 2 ? search.data ?? [] : [];

  return (
    <Dialog title={watching ? 'Asset beobachten' : 'Asset hinzufügen'} onClose={onClose} busy={busy}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <Field id="asset-search" label="Name, Symbol oder ISIN" hint="Euro-Börsen stehen oben, Xetra zuerst.">
          <input className="input" id="asset-search" value={query} autoComplete="off" placeholder="z. B. Nvidia oder DE0007164600"
            onChange={(e) => { setQuery(e.target.value); setPicked(null); setPrice(null); }} {...describe('asset-search', undefined, true)} />
        </Field>
        {query.trim().length >= 2 && (
          search.isFetching && results.length === 0 ? <p className="muted" role="status">Sucht …</p>
            : search.isError ? <p className="err" role="alert">Die Suche ist gerade nicht erreichbar.</p>
              : search.data && results.length === 0 ? <p className="muted" role="status">Nichts gefunden. Versuche es mit dem Symbol oder der ISIN.</p>
                : results.length > 0 && (
                  <div className="results" role="listbox" aria-label="Treffer">
                    {results.map((r) => (
                      <button type="button" key={r.symbol} className="result" role="option" aria-selected={picked?.symbol === r.symbol}
                        onClick={() => { setPicked(r); setPrice(null); }}>
                        <span className="token" aria-hidden="true">{token(r.symbol, r.name)}</span>
                        <span className="grow min0">
                          <span className="trunc">{r.name}</span>
                          <span className="sub-line">{[r.symbol, r.exchange, TYPE_NAMES[r.asset_type]].filter(Boolean).join(' · ')}</span>
                        </span>
                        {!r.eur && <span className="pill pill-warn" title="Kurs wird in Euro umgerechnet">kein Euro</span>}
                      </button>
                    ))}
                  </div>
                )
        )}
        {picked && !watching && (
          <div className="form-grid">
            <Field id="buy-quantity" label="Stück" error={errors.quantity}>
              <input className="input num" id="buy-quantity" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} {...describe('buy-quantity', errors.quantity)} />
            </Field>
            <Field id="buy-price" label="Kaufpreis je Stück" error={errors.price}>
              <input className="input num" id="buy-price" inputMode="decimal" placeholder="€" value={priceText} onChange={(e) => setPrice(e.target.value)} {...describe('buy-price', errors.price)} />
            </Field>
            <div className="full">
              <Field id="buy-date" label="Kaufdatum" error={errors.date}>
                <input className="input" id="buy-date" type="date" max={isoDay(new Date())} value={date} onChange={(e) => setDate(e.target.value)} {...describe('buy-date', errors.date)} />
              </Field>
            </div>
          </div>
        )}
        {!picked && results.length > 0 && <p className="hint">Wähle einen Treffer aus.</p>}
        {picked ? <Actions onCancel={onClose} busy={busy} label={watching ? 'Beobachten' : 'Hinzufügen'} busyLabel="Speichert …" error={errors.form} />
          : <div className="dialog-actions"><button type="button" className="btn" onClick={onClose}>Abbrechen</button></div>}
      </form>
    </Dialog>
  );
}

// ─── Kauf und Verkauf einer Position ───

export function PositionDialog({ row, onClose }: { row: PositionRow; onClose: () => void }) {
  const { eur, qty } = useMoney();
  const [kind, setKind] = useState<'buy' | 'sell'>('buy');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState(fieldAmount(row.current_price ?? row.avg_buy_price));
  const [date, setDate] = useState(isoDay(new Date()));
  const [errors, setErrors] = useState<Errors>({});
  const buy = useBuy();
  const sell = useSell();
  const notify = useToast();
  const busy = buy.isPending || sell.isPending;
  const selling = kind === 'sell';

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const amount = positive(quantity, 'eine Stückzahl', found, 'quantity');
    const unitPrice = positive(price, selling ? 'einen Verkaufspreis' : 'einen Kaufpreis', found, 'price');
    if (selling && amount > row.quantity + 1e-9) found.quantity = `Du hast nur ${qty(row.quantity)} Stück.`;
    if (!selling && !date) found.date = 'Bitte ein Kaufdatum wählen.';
    setErrors(found);
    if (Object.keys(found).length) return;
    try {
      if (selling) {
        await sell.mutateAsync({ asset_id: row.asset_id, quantity: amount, price: unitPrice });
        notify(`Verkauft: ${qty(amount)} × ${row.name} zu ${eur(unitPrice)}`);
      } else {
        await buy.mutateAsync({ asset_id: row.asset_id, quantity: amount, avg_buy_price: unitPrice, bought_at: date });
        notify(`Gekauft: ${qty(amount)} × ${row.name} zu ${eur(unitPrice)}`);
      }
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { quantity: 'quantity', price: 'price', avg_buy_price: 'price', bought_at: 'date' }));
    }
  };

  const lead = <span className="token" aria-hidden="true">{token(row.symbol, row.name)}</span>;
  return (
    <Dialog title={row.name} onClose={onClose} busy={busy} lead={lead}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <p className="muted dialog-sub">{[row.symbol, row.asset_type && TYPE_NAMES[row.asset_type]].filter(Boolean).join(' · ')}</p>
        <div className="strip well">
          <div>
            <div className="kpi-label">Wert</div>
            <div className="kpi-value kpi-small">{eur(row.value)}</div>
            <div className="kpi-sub">{qty(row.quantity)} Stück</div>
          </div>
          <div>
            <div className="kpi-label">Gewinn / Verlust</div>
            <div className={`kpi-value kpi-small ${tone(row.gain)}`}>{eur(row.gain, { sign: true })}</div>
            <div className="kpi-sub">{row.gainPct === null ? '' : `${pct(row.gainPct)} · `}Ø {eur(row.avg_buy_price)}</div>
          </div>
        </div>
        <div className="segmented" role="group" aria-label="Art">
          <button type="button" aria-pressed={!selling} onClick={() => { setKind('buy'); setErrors({}); }}>Kauf</button>
          <button type="button" aria-pressed={selling} onClick={() => { setKind('sell'); setErrors({}); }}>Verkauf</button>
        </div>
        <div className="form-grid">
          <Field id="trade-quantity" label="Stück" error={errors.quantity} hint={selling ? `Höchstens ${qty(row.quantity)}` : undefined}>
            <input className="input num" id="trade-quantity" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)}
              {...describe('trade-quantity', errors.quantity, selling)} />
          </Field>
          <Field id="trade-price" label={selling ? 'Verkaufspreis je Stück' : 'Kaufpreis je Stück'} error={errors.price}>
            <input className="input num" id="trade-price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} {...describe('trade-price', errors.price)} />
          </Field>
          <div className="full">
            {selling
              ? <p className="hint">Der Verkauf wird mit dem heutigen Datum verbucht.</p>
              : (
                <Field id="trade-date" label="Kaufdatum" error={errors.date}>
                  <input className="input" id="trade-date" type="date" max={isoDay(new Date())} value={date} onChange={(e) => setDate(e.target.value)} {...describe('trade-date', errors.date)} />
                </Field>
              )}
          </div>
        </div>
        <Actions onCancel={onClose} busy={busy} label={selling ? 'Verkauf speichern' : 'Kauf speichern'} busyLabel="Speichert …" error={errors.form} />
      </form>
    </Dialog>
  );
}

// ─── Kauf aus der Watchlist ───

export function WatchDialog({ item, onClose }: { item: WatchItem; onClose: () => void }) {
  const { eur, qty } = useMoney();
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState(fieldAmount(item.current_price));
  const [errors, setErrors] = useState<Errors>({});
  const buy = useBuy();
  const unwatch = useUnwatch();
  const notify = useToast();
  const busy = buy.isPending || unwatch.isPending;
  const change = item.current_price && item.price_added ? (item.current_price / item.price_added - 1) * 100 : null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const amount = positive(quantity, 'eine Stückzahl', found, 'quantity');
    const unitPrice = positive(price, 'einen Kaufpreis', found, 'price');
    setErrors(found);
    if (Object.keys(found).length) return;
    try {
      await buy.mutateAsync({ asset_id: item.asset_id, quantity: amount, avg_buy_price: unitPrice, bought_at: isoDay(new Date()) });
      notify(`Gekauft: ${qty(amount)} × ${item.name}, die Position steht jetzt im Portfolio`);
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { quantity: 'quantity', avg_buy_price: 'price' }));
    }
  };

  const remove = () => unwatch.mutate(item.asset_id, {
    onSuccess: () => { notify(`${item.name} von der Watchlist entfernt`); onClose(); },
    onError: (error) => setErrors({ form: error.message }),
  });

  const lead = <span className="token" aria-hidden="true">{token(item.symbol, item.name)}</span>;
  return (
    <Dialog title={item.name} onClose={onClose} busy={busy} lead={lead}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <div className="strip well">
          <div>
            <div className="kpi-label">Kurs</div>
            <div className="kpi-value kpi-small">{item.current_price ? eur(item.current_price) : '–'}</div>
          </div>
          <div>
            <div className="kpi-label">Seit {item.added_at}</div>
            <div className={`kpi-value kpi-small ${change === null ? 'muted' : tone(change)}`}>{change === null ? '–' : pct(change)}</div>
            {item.price_added && <div className="kpi-sub">von {eur(item.price_added)}</div>}
          </div>
        </div>
        <div className="form-grid">
          <Field id="watch-quantity" label="Stück" error={errors.quantity}>
            <input className="input num" id="watch-quantity" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} {...describe('watch-quantity', errors.quantity)} />
          </Field>
          <Field id="watch-price" label="Kaufpreis je Stück" error={errors.price}>
            <input className="input num" id="watch-price" inputMode="decimal" placeholder="€" value={price} onChange={(e) => setPrice(e.target.value)} {...describe('watch-price', errors.price)} />
          </Field>
        </div>
        {errors.form && <p className="err" role="alert">{errors.form}</p>}
        <div className="dialog-actions spread">
          <button type="button" className="btn btn-danger" onClick={remove} disabled={busy}>Von Watchlist entfernen</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>{buy.isPending ? 'Speichert …' : 'Kaufen'}</button>
        </div>
      </form>
    </Dialog>
  );
}

// ─── Sparpläne ───

export type PlanAsset = { asset_id: number; name: string };

export function PlanDialog({ assets, onClose }: { assets: PlanAsset[]; onClose: () => void }) {
  const { eur } = useMoney();
  const [assetId, setAssetId] = useState(assets[0]?.asset_id ?? 0);
  const [amount, setAmount] = useState('');
  const [day, setDay] = useState(Math.min(new Date().getDate(), 28));
  const [errors, setErrors] = useState<Errors>({});
  const create = useCreatePlan();
  const notify = useToast();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const value = positive(amount, 'einen Betrag', found, 'amount');
    setErrors(found);
    if (Object.keys(found).length) return;
    try {
      await create.mutateAsync({ asset_id: assetId, amount: value, day_of_month: day });
      notify(`Sparplan angelegt: ${eur(value)} am ${day}. jedes Monats`);
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { amount: 'amount', day_of_month: 'day', asset_id: 'form' }));
    }
  };

  return (
    <Dialog title="Sparplan anlegen" onClose={onClose} busy={create.isPending}>
      {assets.length === 0
        ? (
          <>
            <p className="empty-line">Ein Sparplan braucht ein Asset aus deinem Depot oder deiner Watchlist. Kaufe oder beobachte zuerst eines.</p>
            <div className="dialog-actions"><button className="btn" onClick={onClose}>Schließen</button></div>
          </>
        )
        : (
          <form className="dialog-form" onSubmit={submit} noValidate>
            <Field id="plan-asset" label="Asset" hint="Aus deinem Depot und deiner Watchlist">
              <select className="select" id="plan-asset" value={assetId} onChange={(e) => setAssetId(Number(e.target.value))} {...describe('plan-asset', undefined, true)}>
                {assets.map((a) => <option key={a.asset_id} value={a.asset_id}>{a.name}</option>)}
              </select>
            </Field>
            <div className="form-grid">
              <Field id="plan-amount" label="Betrag im Monat" error={errors.amount}>
                <input className="input num" id="plan-amount" inputMode="decimal" placeholder="€" value={amount} onChange={(e) => setAmount(e.target.value)} {...describe('plan-amount', errors.amount)} />
              </Field>
              <Field id="plan-day" label="Ausführen am" error={errors.day} hint="Höchstens der 28., den gibt es in jedem Monat">
                <select className="select" id="plan-day" value={day} onChange={(e) => setDay(Number(e.target.value))} {...describe('plan-day', errors.day, true)}>
                  {Array.from({ length: 28 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}.</option>)}
                </select>
              </Field>
            </div>
            <Actions onCancel={onClose} busy={create.isPending} label="Anlegen" busyLabel="Legt an …" error={errors.form} />
          </form>
        )}
    </Dialog>
  );
}

export function DeletePlanDialog({ plan, onClose }: { plan: SavingsPlan; onClose: () => void }) {
  const remove = useDeletePlan();
  const notify = useToast();
  const [error, setError] = useState('');
  const confirm = () => remove.mutate(plan.id, {
    onSuccess: () => { notify(`Sparplan ${plan.asset_name} gelöscht`); onClose(); },
    onError: (e) => setError(e.message),
  });
  return (
    <Dialog title={`Sparplan ${plan.asset_name} löschen?`} onClose={onClose} busy={remove.isPending}>
      <p className="muted">Bereits ausgeführte Käufe bleiben im Portfolio.</p>
      {error && <p className="err" role="alert">{error}</p>}
      <div className="dialog-actions">
        <button className="btn" onClick={onClose} disabled={remove.isPending} data-autofocus>Abbrechen</button>
        <button className="btn btn-danger" onClick={confirm} disabled={remove.isPending}>{remove.isPending ? 'Löscht …' : 'Löschen'}</button>
      </div>
    </Dialog>
  );
}
