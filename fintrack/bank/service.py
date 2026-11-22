"""
bank/service.py - Bankabruf über Enable Banking: verbinden, abrufen, abgleichen, buchen.

Ablauf eines Abrufs je Konto:
1. Umsätze ab synced_until - OVERLAP_DAYS holen (beim ersten Mal ab dem Tag der letzten
   importierten Buchung, damit sich nichts mit früheren CSV-/PDF-Importen überschneidet),
   nur gebuchte (BOOK), vorgemerkte (PDNG) kommen beim nächsten Abruf als gebucht
2. Jeder Umsatz bekommt einen festen Schlüssel (ext_key). Schon bekannte werden übersprungen,
   so schaden überlappende Zeiträume nicht
3. Neue Umsätze laufen durch dieselbe Prüfung wie der Datei-Import (bank_service.build_preview):
   - schon importiert (gleicher Fingerabdruck oder gleicher Tag und Betrag wie ein früher
     importierter Umsatz)            -> 'duplicate', nichts passiert
   - steckt in einer wiederkehrenden Buchung (Miete, Gehalt)  -> 'covered', nichts passiert
   - sichere Kategorie: gleicher Empfänger wie eine frühere Buchung oder eigene Regel
                                     -> wird sofort gebucht ('booked')
   - sonst                           -> 'review', wartet mit Vorschlag auf die Prüfung
4. Kontostand der Bank wird als Kontostand des Tages eingetragen (AccountBalance)
"""

import hashlib
import logging
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from fintrack.api import ApiError
from fintrack.bank.client import BankApiError, EnableBankingClient
from fintrack.contracts.terms import today_berlin
from fintrack.extensions import db
from fintrack.imports.bank_service import _norm, _suggestions, build_preview, description_for
from fintrack.imports.rules import RuleBook
from fintrack.models import (AccountBalance, BankAccount, BankConnection, BankTransaction, Category,
                             Transaction)

logger = logging.getLogger(__name__)

# So viele Tage überlappt jeder Abruf mit dem vorigen (späte Buchungen der Bank)
OVERLAP_DAYS = 5
# Ohne frühere Importe: so weit zurück (viele Banken liefern ohne neue Anmeldung nur 90 Tage)
FIRST_SYNC_DAYS = 89
# Längste Freigabe, die wir anfragen (die meisten Banken erlauben 180 Tage)
MAX_CONSENT = timedelta(days=180)
# Bevorzugte Saldenart: gebuchter Tagesendsaldo zuerst
BALANCE_TYPES = ('CLBD', 'ITBD', 'CLAV', 'ITAV', 'XPCD', 'OPBD', 'PRCD')


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_utc(value):
    """ISO-Zeitpunkt der API -> naive UTC-Zeit, wie sie in der Datenbank steht."""
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def client():
    return EnableBankingClient()


# ─── VERBINDEN ────────────────────────────────────────────────────────────────

def start_connection(user_id, aspsp_name, country, redirect_url, api=None):
    """
    Anmeldung bei der Bank vorbereiten. Gibt die URL der Bank zurück; nach der Anmeldung
    springt die Bank mit code und state zu redirect_url zurück (finish_connection).
    """
    api = api or client()
    banks = {b.get('name'): b for b in api.aspsps(country)}
    bank = banks.get(aspsp_name)
    if not bank:
        raise ApiError(404, 'Diese Bank ist bei Enable Banking nicht verfügbar')
    longest = timedelta(seconds=int(bank.get('maximum_consent_validity') or MAX_CONSENT.total_seconds()))
    # Eine Stunde Sicherheitsabstand: manche Banken lehnen genau das Maximum ab
    valid_until = datetime.now(timezone.utc) + min(longest, MAX_CONSENT) - timedelta(hours=1)

    # Abgebrochene Anmeldungen von früher aufräumen
    BankConnection.query.filter_by(user_id=user_id, status='pending').delete()
    state = secrets.token_urlsafe(32)
    connection = BankConnection(user_id=user_id, aspsp_name=aspsp_name, aspsp_country=country,
                                status='pending', state=state)
    db.session.add(connection)
    db.session.commit()
    try:
        result = api.start_authorization(aspsp_name, country, redirect_url, state, valid_until)
    except BankApiError:
        db.session.delete(connection)
        db.session.commit()
        raise
    return result['url']


def _iban_last4(account):
    identification = account.get('account_id') or {}
    iban = (identification.get('iban') or identification.get('other', {}).get('identification') or '').replace(' ', '')
    return iban[-4:] or None


def finish_connection(state, code, api=None):
    """
    Rücksprung von der Bank: Sitzung anlegen und Konten speichern. Gibt es schon einen
    Zugang zur selben Bank (Erneuern), übernehmen die Konten Auswahl und Abrufstand über
    identification_hash, und der alte Zugang wird entfernt.
    """
    connection = BankConnection.query.filter_by(state=state, status='pending').first() if state else None
    if not connection:
        raise ApiError(404, 'Diese Anmeldung ist unbekannt oder schon abgeschlossen')
    api = api or client()
    session = api.create_session(code)

    previous = {a.identification_hash: a for a in BankAccount.query.join(BankConnection).filter(
        BankConnection.user_id == connection.user_id, BankConnection.aspsp_name == connection.aspsp_name,
        BankConnection.id != connection.id).all()}
    old_connections = BankConnection.query.filter(
        BankConnection.user_id == connection.user_id, BankConnection.aspsp_name == connection.aspsp_name,
        BankConnection.id != connection.id).all()

    connection.session_id = session['session_id']
    connection.status = 'active'
    connection.state = None
    connection.last_error = None
    connection.valid_until = _parse_utc((session.get('access') or {}).get('valid_until'))
    for account in session.get('accounts') or []:
        identification_hash = account.get('identification_hash') or account['uid']
        before = previous.get(identification_hash)
        db.session.add(BankAccount(
            connection_id=connection.id, user_id=connection.user_id, uid=account['uid'],
            identification_hash=identification_hash,
            name=(account.get('name') or account.get('product') or 'Konto')[:200],
            iban_last4=_iban_last4(account), currency=account.get('currency'),
            enabled=before.enabled if before else True,
            synced_until=before.synced_until if before else None,
        ))

    for old in old_connections:
        if old.session_id:
            try:
                api.delete_session(old.session_id)
            except BankApiError:
                logger.warning('Alte Bank-Sitzung %s ließ sich nicht beenden', old.id)
        BankAccount.query.filter_by(connection_id=old.id).delete()
        db.session.delete(old)
    db.session.commit()
    return connection


def remove_connection(connection, api=None):
    """Zugang trennen: Sitzung bei Enable Banking beenden, Zugang und Konten löschen.
    Schon gebuchte Umsätze bleiben im Haushaltsbuch."""
    if connection.session_id:
        try:
            (api or client()).delete_session(connection.session_id)
        except BankApiError:
            logger.warning('Bank-Sitzung %s ließ sich nicht beenden', connection.id)
    BankAccount.query.filter_by(connection_id=connection.id).delete()
    db.session.delete(connection)
    db.session.commit()


# ─── ABRUFEN ──────────────────────────────────────────────────────────────────

@dataclass
class FetchedRow:
    """Ein abgerufener Umsatz, in der Form, die build_preview erwartet."""
    ext_key: str
    day: date
    amount: float
    counterparty: str
    purpose: str
    line: int = 0


def _text(value):
    if isinstance(value, list):
        return ' '.join(str(v).strip() for v in value if v).strip()
    return str(value or '').strip()


def parse_transactions(raw_transactions, identification_hash):
    """API-Umsätze -> FetchedRow; nur gebuchte. Ausgaben negativ, Einnahmen positiv."""
    rows, seen = [], Counter()
    for raw in raw_transactions:
        if (raw.get('status') or 'BOOK') != 'BOOK':
            continue
        money = raw.get('transaction_amount') or {}
        try:
            amount = abs(float(money.get('amount')))
        except (TypeError, ValueError):
            continue
        if not amount or (money.get('currency') or 'EUR') != 'EUR':
            continue
        income = raw.get('credit_debit_indicator') == 'CRDT'
        day_text = raw.get('booking_date') or raw.get('value_date') or raw.get('transaction_date')
        if not day_text:
            continue
        day = date.fromisoformat(str(day_text)[:10])
        # Gegenseite: bei Ausgaben der Empfänger, bei Einnahmen der Auftraggeber
        party = raw.get('debtor') if income else raw.get('creditor')
        counterparty = _text((party or {}).get('name') or raw.get('debtor_name' if income else 'creditor_name'))
        purpose = _text(raw.get('remittance_information'))
        signed = round(amount if income else -amount, 2)

        reference = raw.get('entry_reference')
        if reference:
            raw_key = f'{identification_hash}|ref|{reference}|{day.isoformat()}|{signed:.2f}'
        else:
            # Ohne Referenz: Inhalt plus laufende Nummer gleicher Umsätze (zwei Kaffees am selben Tag)
            content = (day, signed, _norm(counterparty), _norm(purpose))
            raw_key = f'{identification_hash}|content|{day.isoformat()}|{signed:.2f}|{content[2]}|{content[3]}|{seen[content]}'
            seen[content] += 1
        ext_key = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()[:40]
        rows.append(FetchedRow(ext_key, day, signed, counterparty[:500], purpose[:1000]))
    return rows


def _first_sync_start(user_id):
    """Ohne Abrufstand: ab dem Tag der letzten importierten Buchung, sonst 89 Tage zurück."""
    last = db.session.query(db.func.max(Transaction.date)).filter(
        Transaction.user_id == user_id, Transaction.import_hash.isnot(None)).scalar()
    fallback = today_berlin() - timedelta(days=FIRST_SYNC_DAYS)
    if last is None:
        return fallback
    last_day = last.date() if isinstance(last, datetime) else last
    return max(last_day, fallback)


def _confident(row, learned, rules):
    """Sichere Kategorie: gleicher Empfänger wie bei einer früheren Buchung oder eine eigene Regel."""
    by_text, _ = learned
    income = row.amount > 0
    exact = by_text.get((income, _norm(description_for(row.counterparty, row.purpose))))
    if exact:
        return exact, 'learned'
    own = rules.own_rule(income, row.counterparty, row.purpose)
    if own:
        return own, 'rule'
    return None, None


def _imported_lookalikes(user_id, rows):
    """Früher (per Datei) importierte Buchungen je (Tag, Betrag), die zu keinem Bankabruf gehören."""
    days = {r.day for r in rows}
    if not days:
        return Counter()
    start = datetime.combine(min(days), datetime.min.time())
    end = datetime.combine(max(days), datetime.min.time()) + timedelta(days=1)
    from_bank = db.session.query(BankTransaction.transaction_id).filter(
        BankTransaction.user_id == user_id, BankTransaction.transaction_id.isnot(None))
    found = Counter()
    for t in Transaction.query.filter(
            Transaction.user_id == user_id, Transaction.import_hash.isnot(None),
            Transaction.date >= start, Transaction.date < end, Transaction.id.notin_(from_bank)).all():
        found[(t.date.date(), round(t.amount, 2))] += 1
    return found


def process_rows(user_id, rows):
    """Neue Umsätze einordnen und speichern (siehe Modul-Doku). Gibt die Anzahl je Ergebnis zurück."""
    known = {k for (k,) in db.session.query(BankTransaction.ext_key).filter(
        BankTransaction.user_id == user_id, BankTransaction.ext_key.in_([r.ext_key for r in rows] or [''])).all()}
    fresh, keys = [], set()
    for row in rows:
        if row.ext_key not in known and row.ext_key not in keys:
            keys.add(row.ext_key)
            fresh.append(row)
    counts = Counter()
    if not fresh:
        return counts

    lookalikes = _imported_lookalikes(user_id, fresh)
    preview = build_preview(user_id, fresh)
    categories = {c.id: c.type for c in Category.query.filter_by(user_id=user_id).all()}
    learned = _suggestions(user_id, categories)
    rules = RuleBook(user_id)

    for row, entry in zip(fresh, preview):
        record = BankTransaction(user_id=user_id, ext_key=row.ext_key, date=row.day, amount=row.amount,
                                 counterparty=row.counterparty, purpose=row.purpose)
        key = (row.day, round(abs(row.amount), 2))
        if entry['status'] == 'duplicate' or lookalikes[key] > 0:
            if lookalikes[key] > 0:
                lookalikes[key] -= 1
            record.status = 'duplicate'
        elif entry['status'] == 'covered':
            record.status = 'covered'
        else:
            category_id, source = _confident(row, learned, rules)
            kind = categories.get(category_id)
            if category_id and kind and (kind == 'income') == (row.amount > 0) \
                    and not Transaction.query.filter_by(user_id=user_id, import_hash=row.ext_key).count():
                booking = Transaction(user_id=user_id, category_id=category_id, amount=abs(row.amount),
                                      description=description_for(row.counterparty, row.purpose),
                                      date=datetime.combine(row.day, datetime.min.time()),
                                      is_recurring=False, import_hash=row.ext_key)
                db.session.add(booking)
                db.session.flush()
                record.status, record.category_id, record.category_source = 'booked', category_id, source
                record.transaction_id = booking.id
            else:
                record.status = 'review'
                record.category_id, record.category_source = entry['category_id'], entry['category_source']
        counts[record.status] += 1
        db.session.add(record)
    db.session.commit()
    return counts


def _balance_amount(balances):
    """Saldo in Euro nach bevorzugter Saldenart, None ohne passenden Saldo."""
    by_type = {}
    for balance in balances:
        money = balance.get('balance_amount') or {}
        if (money.get('currency') or 'EUR') != 'EUR':
            continue
        try:
            by_type.setdefault(balance.get('balance_type'), float(money['amount']))
        except (KeyError, TypeError, ValueError):
            continue
    for kind in BALANCE_TYPES:
        if kind in by_type:
            return by_type[kind]
    return next(iter(by_type.values()), None)


def _store_balance(user_id, amount, day):
    balance = AccountBalance.query.filter_by(user_id=user_id, date=day).first()
    if balance:
        balance.amount = round(amount, 2)
    else:
        db.session.add(AccountBalance(user_id=user_id, date=day, amount=round(amount, 2)))


def sync_connection(connection, api=None):
    """Alle eingeschalteten Konten eines Zugangs abrufen. Gibt die Anzahl je Ergebnis zurück."""
    api = api or client()
    counts = Counter()
    if connection.valid_until and connection.valid_until <= utcnow():
        connection.status = 'expired'
        db.session.commit()
        return counts
    today = today_berlin()
    total_balance, balance_ok = 0.0, True
    accounts = BankAccount.query.filter_by(connection_id=connection.id, enabled=True).all()
    try:
        for account in accounts:
            start = (account.synced_until - timedelta(days=OVERLAP_DAYS)) if account.synced_until \
                else _first_sync_start(connection.user_id)
            raw = api.transactions(account.uid, start)
            counts.update(process_rows(connection.user_id, parse_transactions(raw, account.identification_hash)))
            account.synced_until = today
            amount = _balance_amount(api.balances(account.uid))
            if amount is None:
                balance_ok = False
            else:
                total_balance += amount
        if accounts and balance_ok:
            _store_balance(connection.user_id, total_balance, today)
            counts['balance'] = round(total_balance, 2)
        connection.last_sync_at = utcnow()
        connection.last_error = None
    except BankApiError as error:
        db.session.rollback()
        if error.session_expired:
            connection.status = 'expired'
            connection.last_error = 'Die Freigabe bei der Bank ist abgelaufen. Bitte neu verbinden.'
        elif error.rate_limited:
            connection.last_error = 'Die Bank erlaubt gerade keine weiteren Abrufe. Später noch einmal versuchen.'
        else:
            connection.last_error = f'Enable Banking: {error}'[:500]
        logger.warning('Bankabruf für Zugang %s fehlgeschlagen: %s', connection.id, error)
        db.session.commit()
        raise
    db.session.commit()
    return counts


def sync_user(user_id, api=None):
    """Alle aktiven Zugänge eines Nutzers abrufen. Fehler eines Zugangs stoppen die anderen nicht."""
    counts, errors = Counter(), []
    for connection in BankConnection.query.filter_by(user_id=user_id, status='active').all():
        try:
            counts.update(sync_connection(connection, api))
        except BankApiError as error:
            errors.append(connection.last_error or str(error))
    return counts, errors


def sync_all_users():
    """Für den nächtlichen Lauf: alle Nutzer mit aktivem Bankzugang."""
    from fintrack.bank.client import is_configured
    if not is_configured():
        return {'bank': 'nicht eingerichtet'}
    api = client()
    summary = Counter()
    users = {c.user_id for c in BankConnection.query.filter_by(status='active').all()}
    for user_id in users:
        counts, errors = sync_user(user_id, api)
        summary.update({k: v for k, v in counts.items() if k != 'balance'})
        summary['errors'] += len(errors)
    return dict(summary)


# ─── PRÜFEN ───────────────────────────────────────────────────────────────────

def review_rows(user_id):
    """Wartende Umsätze in der Form der Import-Vorschau (key 'bank-<id>')."""
    rows = BankTransaction.query.filter_by(user_id=user_id, status='review') \
        .order_by(BankTransaction.date.desc(), BankTransaction.id.desc()).all()
    return [{
        "key": f'bank-{r.id}', "occurrence": 0, "line": r.id, "date": r.date.isoformat(), "amount": r.amount,
        "counterparty": r.counterparty, "purpose": r.purpose,
        "description": description_for(r.counterparty, r.purpose),
        "status": 'new', "covered_by": None, "category_id": r.category_id, "category_source": r.category_source,
    } for r in rows]


def commit_review(user_id, book, dismiss):
    """
    Geprüfte Umsätze buchen (book: [{id, category_id, description}]) und den Rest verwerfen
    (dismiss: [id]). Alles oder nichts.
    """
    categories = {c.id: c.type for c in Category.query.filter_by(user_id=user_id).all()}
    ids = [entry.id for entry in book] + list(dismiss)
    rows = {r.id: r for r in BankTransaction.query.filter(
        BankTransaction.user_id == user_id, BankTransaction.id.in_(ids or [0])).all()}
    for entry in book:
        row = rows.get(entry.id)
        if row is None or row.status != 'review':
            raise ApiError(404, 'Umsatz nicht gefunden oder schon bearbeitet')
        kind = categories.get(entry.category_id)
        if kind is None:
            raise ApiError(404, 'Kategorie nicht gefunden')
        if (kind == 'income') != (row.amount > 0):
            raise ApiError(400, f'{description_for(row.counterparty, row.purpose)}: Einnahmen gehören in eine '
                                f'Einkommens-, Ausgaben in eine Ausgaben-Kategorie')

    booked = 0
    for entry in book:
        row = rows[entry.id]
        existing = Transaction.query.filter_by(user_id=user_id, import_hash=row.ext_key).first()
        booking = existing or Transaction(
            user_id=user_id, category_id=entry.category_id, amount=abs(row.amount),
            description=(entry.description or description_for(row.counterparty, row.purpose))[:200],
            date=datetime.combine(row.date, datetime.min.time()), is_recurring=False, import_hash=row.ext_key)
        if not existing:
            db.session.add(booking)
            db.session.flush()
            booked += 1
        row.status, row.category_id, row.transaction_id = 'booked', entry.category_id, booking.id
    dismissed = 0
    for row_id in dismiss:
        row = rows.get(row_id)
        if row is not None and row.status == 'review':
            row.status = 'dismissed'
            dismissed += 1
    db.session.commit()
    return booked, dismissed


def review_count(user_id):
    return BankTransaction.query.filter_by(user_id=user_id, status='review').count()
