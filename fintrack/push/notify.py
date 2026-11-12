"""
push/notify.py - Welche Meldungen der Morgen-Lauf (jobs.py, 8:00 Uhr) verschickt:

- Kündigungsfristen: 14 Tage und 3 Tage vor dem letzten Kündigungstag eines Vertrags
- Sparplan fällig: am Ausführungstag, solange er noch nicht bestätigt ist
- Tages-Update: ein Hinweis, dass der KI-Text vom Vorabend bereitliegt

Alle drei entstehen über Nacht (Datumswechsel, KI-Lauf um 22:30) und gehen deshalb
nach der Ruhezeit (22-8 Uhr) mit dem Morgen-Lauf raus. Jede Meldung einzeln und nur einmal
(PushLog). Fällt ein Lauf aus, holt der nächste Verpasstes nach, solange es noch gilt.
Inhalt ohne Beträge, weil Meldungen auf dem Sperrbildschirm stehen.
"""

from datetime import datetime, timedelta

from fintrack.contracts.terms import contract_status, today_berlin
from fintrack.extensions import db
from fintrack.models import Asset, Contract, DailyInsight, PushLog, PushSubscription, SavingsPlan
from fintrack.portfolio.savings_plans import due_date_this_month, is_due
from fintrack.push.service import send_to_user, vapid_keys

# Erinnerungen so viele Tage vor dem letzten Kündigungstag
REMINDER_DAYS = (14, 3)


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
    sent = send_to_user(user_id, 'daily_update', 'Dein Tages-Update ist da',
                        'Was sich in Depot und Haushaltsbuch getan hat.', url='/app/', tag='daily-update')
    _remember(user_id, key)
    return sent


def notify_all_users(today=None, now=None):
    """Morgen-Lauf für alle Nutzer mit mindestens einem angemeldeten Gerät."""
    if not vapid_keys():
        return {'push': 'nicht eingerichtet'}
    today = today or today_berlin()
    now = now or datetime.now()
    user_ids = [row[0] for row in db.session.query(PushSubscription.user_id).distinct()]
    summary = {'users': len(user_ids), 'deadlines': 0, 'savings_plan': 0, 'daily_update': 0}
    for user_id in user_ids:
        summary['deadlines'] += notify_deadlines(user_id, today)
        summary['savings_plan'] += notify_savings_plans(user_id, now)
        summary['daily_update'] += notify_daily_update(user_id, now)
    return summary
