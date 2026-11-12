"""
push/alerts.py - Kursprüfung tagsüber für Push-Meldungen (jobs.py: alle 30 Minuten
von 9:00 bis 21:30 Uhr, also nie in der Ruhezeit 22-8 Uhr):

- Starke Kursbewegung einer Position: mindestens POSITION_MOVE gegenüber dem
  letzten Schlusskurs, höchstens eine Meldung pro Position, Tag und Richtung
- Starke Bewegung des ganzen Depots: mindestens DEPOT_MOVE, ebenso einmal pro Tag
  und Richtung; erst ab zwei Positionen, sonst wäre es dieselbe Meldung doppelt
- Watchlist-Zielkurs erreicht: einmalig, danach gilt das Ziel als erreicht

Neon-Datenbank schonen: Neon rechnet Rechenzeit ab und schläft nach ein paar Minuten
ohne Anfrage ein. Eine Prüfung alle 30 Minuten darf sie deshalb nicht jedes Mal
wecken. Alles, was die Prüfung aus der Datenbank braucht (Positionen, letzte
Schlusskurse, Zielkurse, Wechselkurse, schon verschickte Meldungen), liegt in einem
Zwischenspeicher im Arbeitsspeicher (_Snapshot). Er wird nur neu gebaut, wenn sich
Positionen, Watchlist oder Push-Geräte geändert haben (SQLAlchemy-Ereignis unten),
an einem neuen Tag oder nach dem abendlichen Kurs-Lauf. Eine Prüfung ohne Treffer
fragt nur die Live-Kurse bei yfinance ab; die Datenbank wird erst angefasst, wenn
wirklich eine Meldung rausgeht. Das passt zum einzigen Gunicorn-Worker.

Meldungen ohne Zahlen: weder Beträge noch Prozente, nur Richtung und Schwelle.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import event
from sqlalchemy.orm import Session

from fintrack.contracts.terms import today_berlin
from fintrack.extensions import db
from fintrack.market import quotes
from fintrack.market.service import latest_fx_rate
from fintrack.models import Asset, PriceHistory, PushLog, PushSubscription, UserAsset, Watchlist
from fintrack.push.service import send_to_user, vapid_keys

logger = logging.getLogger(__name__)

POSITION_MOVE = 0.05
DEPOT_MOVE = 0.03
# Ist der letzte gespeicherte Schlusskurs älter, ist der Vergleich nicht aussagekräftig
# (z.B. weil der Kurs-Lauf ein paar Tage ausgefallen ist)
MAX_CLOSE_AGE_DAYS = 5
QUIET_START, QUIET_END = 22, 8


@dataclass
class _Holding:
    asset_id: int
    symbol: str
    name: str
    quantity: float
    currency: str
    previous_close: float  # in der Handelswährung, wie der Live-Kurs


@dataclass
class _Target:
    watch_id: int
    symbol: str
    name: str
    target: float  # in Euro
    direction: str  # 'above' oder 'below'


@dataclass
class _UserChecks:
    holdings: list = field(default_factory=list)
    targets: list = field(default_factory=list)


@dataclass
class _Snapshot:
    day: date
    users: dict  # user_id -> _UserChecks
    fx: dict  # Währung -> Wert von 1 Einheit in Euro
    sent: set  # schon verschickte Schlüssel von heute (PushLog)


_lock = threading.Lock()
_state = {'snapshot': None, 'dirty': True}


def invalidate():
    """Zwischenspeicher bei der nächsten Prüfung neu bauen."""
    _state['dirty'] = True


@event.listens_for(Session, 'before_flush')
def _watch_changes(session, flush_context, instances):
    """Ändern sich Positionen, Watchlist oder Push-Geräte, gilt der Zwischenspeicher als veraltet."""
    watched = (UserAsset, Watchlist, PushSubscription)
    if any(isinstance(obj, watched) for obj in (*session.new, *session.dirty, *session.deleted)):
        invalidate()


def _last_close(asset_id, today):
    """Letzter gespeicherter Schlusskurs vor heute als (Kurs, Währung), oder None, wenn zu alt."""
    row = PriceHistory.query.filter(
        PriceHistory.asset_id == asset_id, PriceHistory.price.isnot(None),
        PriceHistory.date < datetime.combine(today, datetime.min.time())) \
        .order_by(PriceHistory.date.desc()).first()
    if not row or (today - row.date.date()).days > MAX_CLOSE_AGE_DAYS:
        return None
    return row.price, row.currency


def _build(today):
    """Liest einmal alles, was die Prüfungen brauchen. Nur für Nutzer mit eingeschaltetem Gerät."""
    users, currencies = {}, set()
    subscriptions = PushSubscription.query.filter(
        db.or_(PushSubscription.price_moves.is_(True), PushSubscription.watchlist.is_(True))).all()
    wants = {}
    for subscription in subscriptions:
        moves, targets = wants.get(subscription.user_id, (False, False))
        wants[subscription.user_id] = (moves or subscription.price_moves, targets or subscription.watchlist)

    for user_id, (moves, targets) in wants.items():
        checks = _UserChecks()
        if moves:
            rows = db.session.query(UserAsset, Asset).join(Asset, Asset.id == UserAsset.asset_id) \
                .filter(UserAsset.user_id == user_id, UserAsset.quantity > 0).all()
            for position, asset in rows:
                close = _last_close(asset.id, today)
                if close:
                    checks.holdings.append(_Holding(asset.id, asset.symbol, asset.name, position.quantity,
                                                    close[1] or asset.currency or 'EUR', close[0]))
        if targets:
            rows = db.session.query(Watchlist, Asset).join(Asset, Asset.id == Watchlist.asset_id) \
                .filter(Watchlist.user_id == user_id, Watchlist.target_price.isnot(None),
                        Watchlist.target_hit_at.is_(None)).all()
            for item, asset in rows:
                checks.targets.append(_Target(item.id, asset.symbol, asset.name, item.target_price,
                                              item.target_direction or 'above'))
                currencies.add(asset.currency or 'EUR')
        users[user_id] = checks
        currencies.update(h.currency for h in checks.holdings)

    fx = {currency: latest_fx_rate(currency) for currency in currencies | {'EUR'}}
    sent = {row.key for row in PushLog.query.filter(PushLog.key.contains(f':{today.isoformat()}:')).all()}
    return _Snapshot(today, users, fx, sent)


def _snapshot(today):
    snapshot = _state['snapshot']
    if _state['dirty'] or snapshot is None or snapshot.day != today:
        _state['dirty'] = False
        snapshot = _state['snapshot'] = _build(today)
        db.session.commit()  # Lese-Transaktion beenden
    return snapshot


def _live_prices(symbols):
    """Live-Kurse ohne Datenbank: Symbol -> (Kurs, Währung)."""
    prices = {}
    for symbol in symbols:
        quote = quotes.fetch_last_price(symbol)
        if quote:
            prices[symbol] = quote
    return prices


def _notify_once(snapshot, user_id, key, topic, title, body, url, tag):
    """Schickt eine Meldung, wenn sie heute noch nicht rausging (auch nicht vor einem Neustart)."""
    if key in snapshot.sent:
        return 0
    snapshot.sent.add(key)
    if PushLog.query.filter_by(user_id=user_id, key=key).first():
        return 0
    sent = send_to_user(user_id, topic, title, body, url=url, tag=tag)
    db.session.add(PushLog(user_id=user_id, key=key))
    db.session.commit()
    return sent


def _direction(change):
    return 'up' if change > 0 else 'down'


def _check_user(snapshot, user_id, checks, live, today):
    summary = {'moves': 0, 'depot': 0, 'targets': 0}
    day = today.isoformat()
    depot_now = depot_before = 0.0
    priced = 0

    for holding in checks.holdings:
        quote = live.get(holding.symbol)
        if not quote or quote[1] != holding.currency or holding.previous_close <= 0:
            continue
        rate = snapshot.fx.get(holding.currency)
        if rate:
            depot_now += holding.quantity * quote[0] * rate
            depot_before += holding.quantity * holding.previous_close * rate
            priced += 1
        change = quote[0] / holding.previous_close - 1
        if abs(change) < POSITION_MOVE:
            continue
        up = change > 0
        summary['moves'] += _notify_once(
            snapshot, user_id, f'move:{holding.asset_id}:{day}:{_direction(change)}', 'price_moves',
            f'{holding.name} heute deutlich im {"Plus" if up else "Minus"}',
            f'Mehr als {round(POSITION_MOVE * 100)} % {"über" if up else "unter"} dem letzten Schlusskurs.',
            '/app/portfolio', f'move-{holding.asset_id}')

    if priced >= 2 and depot_before > 0:
        change = depot_now / depot_before - 1
        if abs(change) >= DEPOT_MOVE:
            up = change > 0
            summary['depot'] += _notify_once(
                snapshot, user_id, f'depot:{user_id}:{day}:{_direction(change)}', 'price_moves',
                f'Dein Depot heute deutlich im {"Plus" if up else "Minus"}',
                f'Mehr als {round(DEPOT_MOVE * 100)} % {"über" if up else "unter"} dem letzten Handelstag.',
                '/app/portfolio', 'depot-move')

    for target in list(checks.targets):
        quote = live.get(target.symbol)
        rate = snapshot.fx.get(quote[1]) if quote else None
        if not rate:
            continue
        price = quote[0] * rate
        reached = price >= target.target if target.direction == 'above' else price <= target.target
        if not reached:
            continue
        checks.targets.remove(target)
        item = db.session.get(Watchlist, target.watch_id)
        if not item or item.target_price != target.target or item.target_hit_at:
            continue  # inzwischen geändert oder gelöscht
        item.target_hit_at = datetime.now()
        db.session.commit()
        summary['targets'] += _notify_once(
            snapshot, user_id, f'target:{target.watch_id}:{target.target}', 'watchlist',
            f'{target.name}: Zielkurs erreicht',
            'Der Kurs ist über deinen Zielkurs gestiegen.' if target.direction == 'above'
            else 'Der Kurs ist unter deinen Zielkurs gefallen.',
            '/app/portfolio', f'target-{target.watch_id}')
    return summary


def _ensure_fx(snapshot, live):
    """Für Zielkurse in anderen Währungen fehlende Wechselkurse einmal nachladen."""
    missing = {quote[1] for quote in live.values()} - set(snapshot.fx)
    for currency in missing:
        snapshot.fx[currency] = latest_fx_rate(currency)


def run_price_alerts(flask_app):
    """Für den Scheduler: eine Prüfung im App-Kontext, Fehler nur ins Log."""
    with flask_app.app_context():
        try:
            summary = check_price_alerts()
            logger.info('Kursprüfung: %s', summary)
            return summary
        except Exception:
            db.session.rollback()
            logger.exception('Kursprüfung fehlgeschlagen')
            return None


def check_price_alerts(now=None, today=None):
    """
    Eine Prüfung. Gibt eine Zusammenfassung zurück; läuft nie in der Ruhezeit.
    now ist deutsche Zeit (der Server läuft in UTC).
    """
    now = now or datetime.now(ZoneInfo('Europe/Berlin'))
    if not vapid_keys():
        return {'push': 'nicht eingerichtet'}
    if now.hour >= QUIET_START or now.hour < QUIET_END:
        return {'push': 'Ruhezeit'}
    if not _lock.acquire(blocking=False):
        return {'push': 'läuft bereits'}
    try:
        today = today or today_berlin()
        snapshot = _snapshot(today)
        symbols = {h.symbol for c in snapshot.users.values() for h in c.holdings} | \
                  {t.symbol for c in snapshot.users.values() for t in c.targets}
        live = _live_prices(sorted(symbols))
        if any(quote[1] not in snapshot.fx for quote in live.values()):
            _ensure_fx(snapshot, live)
            db.session.commit()
        summary = {'users': len(snapshot.users), 'symbols': len(live), 'moves': 0, 'depot': 0, 'targets': 0}
        for user_id, checks in snapshot.users.items():
            for key, value in _check_user(snapshot, user_id, checks, live, today).items():
                summary[key] += value
        return summary
    finally:
        _lock.release()
