"""
jobs.py - Tägliche Hintergrundjobs und ihr Scheduler.

Ein Lauf besteht aus drei Schritten in fester Reihenfolge:
1. Kurse und Wechselkurse aktualisieren (market/service.py)
2. neue Dividenden verbuchen (braucht aktuelle Wechselkurse)
3. tägliche KI-Insights erzeugen (braucht aktuelle Kurse)

Gestartet wird der Lauf auf zwei Wegen, die sich nicht in die Quere kommen:
- vom Scheduler im Server, abends um 22:30 Uhr deutscher Zeit
- von GitHub Actions über /api/v1/admin/run-daily-jobs, das den Server
  vorher aufweckt - auf dem kostenlosen Render-Tarif schläft er sonst
Eine Sperre sorgt dafür, dass immer nur ein Lauf gleichzeitig arbeitet.
"""

import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from fintrack.extensions import get_openai_client
from fintrack.insights.service import generate_insights_for_all_users
from fintrack.market.service import update_all_prices
from fintrack.portfolio.dividends import process_dividends_for_all_users

logger = logging.getLogger(__name__)

TIMEZONE = 'Europe/Berlin'

# Zustand des letzten Laufs - liegt im Speicher des (einzigen) Workers
_lock = threading.Lock()
_status = {'state': 'idle', 'job': None, 'started_at': None, 'finished_at': None,
           'result': None, 'error': None}


def update_prices(flask_app):
    with flask_app.app_context():
        summary = update_all_prices()
        logger.info('Kurse aktualisiert: %s', summary)
        return summary


def check_dividends(flask_app):
    """Neue Dividenden aller Nutzer erkennen und im Haushaltsbuch verbuchen."""
    with flask_app.app_context():
        process_dividends_for_all_users()
        return {'dividends': 'geprüft'}


def generate_daily_insights(flask_app):
    """Den täglichen KI-Insight für alle Nutzer erzeugen (höchstens einen pro Tag)."""
    with flask_app.app_context():
        created = generate_insights_for_all_users(get_openai_client())
        return {'insights': created}


def run_daily_jobs(flask_app):
    """Alle drei Schritte nacheinander. Ein Fehler in einem Schritt stoppt die folgenden nicht."""
    result = {}
    for name, job in (('prices', update_prices), ('dividends', check_dividends),
                      ('insights', generate_daily_insights)):
        try:
            result[name] = job(flask_app)
        except Exception as error:
            logger.exception('Schritt %s des täglichen Laufs ist fehlgeschlagen', name)
            result[name] = {'error': str(error)}
    return result


JOBS = {
    'daily': run_daily_jobs,
    'prices': update_prices,
    'dividends': check_dividends,
    'insights': generate_daily_insights,
}


def _run(flask_app, job_name):
    try:
        result = JOBS[job_name](flask_app)
        failed = any(isinstance(step, dict) and step.get('error') for step in (result or {}).values()) \
            if job_name == 'daily' else False
        _status.update(state='failed' if failed else 'done', result=result,
                       error='Mindestens ein Schritt ist fehlgeschlagen' if failed else None)
    except Exception as error:
        logger.exception('Job %s ist fehlgeschlagen', job_name)
        _status.update(state='failed', error=str(error))
    finally:
        _status['finished_at'] = datetime.now().isoformat(timespec='seconds')
        _lock.release()


def start_job(flask_app, job_name, background=True):
    """
    Startet einen Job, wenn gerade keiner läuft. Gibt False zurück, wenn
    schon ein Lauf arbeitet. Im Hintergrund, damit HTTP-Anfragen sofort
    antworten - das erste Laden eines Jahres an Kursen dauert länger als
    das Zeitlimit eines Requests.
    """
    if not _lock.acquire(blocking=False):
        return False
    _status.update(state='running', job=job_name, started_at=datetime.now().isoformat(timespec='seconds'),
                   finished_at=None, result=None, error=None)
    if background:
        threading.Thread(target=_run, args=(flask_app, job_name), daemon=True).start()
    else:
        _run(flask_app, job_name)
    return True


def job_status():
    return dict(_status)


def start_scheduler(flask_app):
    """
    Startet den Scheduler: jeden Abend um 22:30 Uhr deutscher Zeit (nach
    US-Börsenschluss) den kompletten täglichen Lauf.
    """
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(start_job, 'cron', hour=22, minute=30, args=[flask_app, 'daily'])
    scheduler.start()
    print(f'Scheduler started - daily jobs 22:30 {TIMEZONE}')
