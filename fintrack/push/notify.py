"""
push/notify.py - Welche Meldungen der Morgen-Lauf (jobs.py, 8:00 Uhr) verschickt:

- Kündigungsfristen: 14 Tage und 3 Tage vor dem letzten Kündigungstag eines Vertrags
- Sparplan fällig: am Ausführungstag, solange er noch nicht bestätigt ist
- Tages-Update: ein Hinweis, dass der KI-Text vom Vorabend bereitliegt
- Bankabruf: Umsätze warten auf Prüfung (wie das Tages-Update), Freigabe der Bank läuft
  in 7 bzw. 1 Tag ab oder ist abgelaufen (wie die Kündigungsfristen)

Alle drei entstehen über Nacht (Datumswechsel, KI-Lauf um 22:30) und gehen deshalb
nach der Ruhezeit (22-8 Uhr) mit dem Morgen-Lauf raus. Jede Meldung einzeln und nur einmal
(PushLog). Fällt ein Lauf aus, holt der nächste Verpasstes nach, solange es noch gilt.
Inhalt ohne Beträge, weil Meldungen auf dem Sperrbildschirm stehen.
"""

import json
from datetime import datetime, timedelta

from fintrack.contracts.terms import contract_status, today_berlin
from fintrack.extensions import db
from fintrack.models import (Asset, BankConnection, BankTransaction, Contract, DailyInsight, PushLog,
                             PushSubscription, SavingsPlan)
from fintrack.portfolio.savings_plans import due_date_this_month, is_due
from fintrack.push.service import send_to_user, vapid_keys

# Erinnerungen so viele Tage vor dem letzten Kündigungstag
REMINDER_DAYS = (14, 3)
# Erinnerungen so viele Tage, bevor die Freigabe der Bank abläuft
BANK_REMINDER_DAYS = (7, 1)


def _already_sent(user_id, key):
    return PushLog.query.filter_by(user_id=user_id, key=key).first() is not None


def _remember(user_id, key):
    db.session.add(PushLog(user_id=user_id, key=key))
    db.session.commit()


def _deadline_text(days_left, cancel_by):
    when = cancel_by.strftime('%d.%m.%Y')
    if days_left == 0:
        return f'Heute ist der letzte Tag zum Kündigen ({when}).'
    if days_left == 1:
        return f'Morgen ist der letzte Tag zum Kündigen ({when}).'
    return f'Noch {days_left} Tage zum Kündigen, bis {when}.'


def notify_deadlines(user_id, today):
    """Erinnerungen an Kündigungsfristen. Gibt die Anzahl verschickter Meldungen zurück."""
    sent = 0
    for contract in Contract.query.filter_by(user_id=user_id).all():
        status = contract_status(contract, today)
        cancel_by = status['cancel_by']
        if not cancel_by:
            continue
        days_left = (cancel_by - today).days
        # Nur die engste fällige Stufe; ältere Stufen gelten damit als erledigt
        due = [days for days in REMINDER_DAYS if days_left <= days]
        if not due:
            continue
        key = f'contract:{contract.id}:{cancel_by.isoformat()}:{min(due)}'
        if _already_sent(user_id, key):
            continue
        sent += send_to_user(user_id, 'deadlines', f'Kündigungsfrist: {contract.name}',
                             _deadline_text(days_left, cancel_by), url='/app/contracts',
                             tag=f'contract-{contract.id}')
        _remember(user_id, key)
    return sent


def notify_savings_plans(user_id, now):
    """Fällige, noch nicht bestätigte Sparpläne; einmal pro Plan und Fälligkeitstag."""
    sent = 0
    for plan in SavingsPlan.query.filter_by(user_id=user_id, active=True).all():
        if not is_due(plan, now):
            continue
        key = f'plan:{plan.id}:{due_date_this_month(plan, now).date().isoformat()}'
        if _already_sent(user_id, key):
            continue
        asset = db.session.get(Asset, plan.asset_id)
        name = asset.name if asset else 'Sparplan'
        sent += send_to_user(user_id, 'savings_plan', f'Sparplan fällig: {name}',
                             'Bestätige die Ausführung in FinTrack, sobald sie gebucht ist.',
                             url='/app/portfolio', tag=f'plan-{plan.id}')
        _remember(user_id, key)
    return sent


def notify_daily_update(user_id, now):
    """Hinweis auf das Tages-Update der letzten 24 Stunden, ohne Inhalt (Sperrbildschirm)."""
    insight = DailyInsight.query.filter(DailyInsight.user_id == user_id,
                                        DailyInsight.created_at >= now - timedelta(hours=24)) \
        .order_by(DailyInsight.created_at.desc()).first()
    if not insight:
        return 0
    key = f'insight:{insight.id}'
    if _already_sent(user_id, key):
        return 0
    # Nur die Anzahl, keine Namen: sie würden auf dem Sperrbildschirm verraten, was im Depot liegt
    count = len(json.loads(insight.news)) if insight.news else 0
    body = ('Was sich in Depot und Haushaltsbuch getan hat.' if not count
            else 'Mit News zu einem Wert aus deinem Depot.' if count == 1
            else f'Mit News zu {count} Werten aus deinem Depot.')
    sent = send_to_user(user_id, 'daily_update', 'Dein Tages-Update ist da', body, url='/app/', tag='daily-update')
    _remember(user_id, key)
    return sent


def notify_bank(user_id, today):
    """Wartende Umsätze vom Bankabruf und ablaufende Bank-Freigaben."""
    sent = 0
    waiting = BankTransaction.query.filter_by(user_id=user_id, status='review').count()
    key = f'bank-review:{today.isoformat()}'
    if waiting and not _already_sent(user_id, key):
        body = '1 Umsatz wartet auf deine Prüfung.' if waiting == 1 else f'{waiting} Umsätze warten auf deine Prüfung.'
        sent += send_to_user(user_id, 'daily_update', 'Neue Umsätze von der Bank', body,
                             url='/app/budget/import?source=bank', tag='bank-review')
        _remember(user_id, key)

    for connection in BankConnection.query.filter(BankConnection.user_id == user_id,
                                                  BankConnection.status.in_(('active', 'expired'))).all():
        if not connection.valid_until:
            continue
        end = connection.valid_until.date()
        days_left = (end - today).days
        if connection.status == 'expired' or days_left < 0:
            key, title = f'bank-expired:{connection.id}:{end.isoformat()}', 'Bankzugang abgelaufen'
            body = f'Die Freigabe für {connection.aspsp_name} ist abgelaufen. Verbinde die Bank in den Einstellungen neu.'
        else:
            due = [days for days in BANK_REMINDER_DAYS if days_left <= days]
            if not due:
                continue
            key, title = f'bank-expiry:{connection.id}:{end.isoformat()}:{min(due)}', 'Bankzugang läuft ab'
            when = 'morgen' if days_left == 1 else 'heute' if days_left == 0 else f'in {days_left} Tagen'
            body = f'Die Freigabe für {connection.aspsp_name} endet {when}. In den Einstellungen erneuern.'
        if _already_sent(user_id, key):
            continue
        sent += send_to_user(user_id, 'deadlines', title, body, url='/app/settings', tag=f'bank-{connection.id}')
        _remember(user_id, key)
    return sent


def notify_all_users(today=None, now=None):
    """Morgen-Lauf für alle Nutzer mit mindestens einem angemeldeten Gerät."""
    if not vapid_keys():
        return {'push': 'nicht eingerichtet'}
    today = today or today_berlin()
    now = now or datetime.now()
    user_ids = [row[0] for row in db.session.query(PushSubscription.user_id).distinct()]
    summary = {'users': len(user_ids), 'deadlines': 0, 'savings_plan': 0, 'daily_update': 0, 'bank': 0}
    for user_id in user_ids:
        summary['deadlines'] += notify_deadlines(user_id, today)
        summary['savings_plan'] += notify_savings_plans(user_id, now)
        summary['daily_update'] += notify_daily_update(user_id, now)
        summary['bank'] += notify_bank(user_id, today)
    return summary
