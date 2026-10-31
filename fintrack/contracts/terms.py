"""
contracts/terms.py - Laufzeiten und Kündigungsfristen von Verträgen.

Reine Berechnung ohne Datenbank, damit sich jeder Fall einzeln testen lässt.

Begriffe:
- Laufzeitende: letzter Tag einer Laufzeit. Ein Vertrag ab 01.01.2026 mit
  12 Monaten läuft bis 31.12.2026, danach beginnt die nächste Laufzeit.
- Kündigungstag: letzter Tag, an dem die Kündigung beim Anbieter sein muss,
  damit der Vertrag zum Laufzeitende endet. Bei 3 Monaten Frist zum 31.12.
  ist das der 30.09.
"""

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Zahlungen pro Jahr je Zahlweise
PAYMENTS_PER_YEAR = {'monthly': 12, 'quarterly': 4, 'half_yearly': 2, 'yearly': 1}


def today_berlin():
    """Heutiges Datum in Deutschland (der Server läuft in UTC)."""
    return datetime.now(ZoneInfo('Europe/Berlin')).date()


def add_months(day, months):
    """Monate addieren (auch negativ); der Tag wird aufs Monatsende gekürzt, z.B. 31.01. + 1 = 28.02."""
    month_index = day.year * 12 + day.month - 1 + months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def term_end(start_date, months):
    """
    Letzter Tag einer Laufzeit von `months` Monaten ab start_date (wie § 188 BGB):
    der Tag vor dem gleichen Kalendertag, oder das Monatsende, wenn es den Tag
    im Zielmonat nicht gibt (ab 31.01. für 1 Monat -> 28.02.).
    """
    same_day = add_months(start_date, months)
    if same_day.day < start_date.day:
        return same_day
    return same_day - timedelta(days=1)


def notice_deadline(end, notice_value, notice_unit):
    """
    Kündigungstag für ein Laufzeitende. Monate werden vom Tag nach dem
    Laufzeitende zurückgerechnet, damit Monatsenden stimmen:
    31.12. mit 3 Monaten -> 30.09., 30.04. mit 1 Monat -> 31.03.
    """
    if notice_unit == 'months':
        return add_months(end + timedelta(days=1), -notice_value) - timedelta(days=1)
    days = notice_value * 7 if notice_unit == 'weeks' else notice_value
    return end - timedelta(days=days)


def _term_ends(contract):
    """Alle Laufzeitenden des Vertrags in zeitlicher Reihenfolge (endlos, solange er sich verlängert)."""
    first = contract.min_term_months or contract.renewal_months
    if not first:
        return
    yield term_end(contract.start_date, first)
    if not contract.renewal_months:
        return
    step = 1
    while True:
        # Immer vom Startdatum aus rechnen, sonst wandert ein 31. durch kurze Monate
        yield term_end(contract.start_date, first + step * contract.renewal_months)
        step += 1


def contract_status(contract, today):
    """
    Stand eines Vertrags an einem Tag:
    - status: 'active' (läuft weiter), 'cancelled' (gekündigt, endet noch),
      'ending' (endet ohne Kündigung von selbst), 'ended' (schon beendet)
    - next_term_end: nächstes Laufzeitende ab heute (verlängert sich danach)
    - cancel_by / cancel_effective: bis wann man spätestens kündigen muss und
      zu welchem Laufzeitende der Vertrag dann endet. Ist die Frist für das
      nächste Ende schon vorbei, gilt das übernächste.
    - ends_on: Ende eines gekündigten oder auslaufenden Vertrags
    """
    result = {'status': 'active', 'next_term_end': None, 'cancel_by': None,
              'cancel_effective': None, 'ends_on': None}

    if contract.end_date:
        result['ends_on'] = contract.end_date
        result['status'] = 'ended' if contract.end_date < today else 'cancelled'
        return result

    if not contract.renewal_months:
        # Feste Laufzeit ohne Verlängerung: endet von selbst, keine Kündigung nötig
        end = next(_term_ends(contract), None)
        result['ends_on'] = end
        result['status'] = 'ended' if end and end < today else 'ending'
        return result

    for end in _term_ends(contract):
        if end < today:
            continue
        if result['next_term_end'] is None:
            result['next_term_end'] = end
        deadline = notice_deadline(end, contract.notice_value, contract.notice_unit)
        if deadline >= today:
            result['cancel_by'] = deadline
            result['cancel_effective'] = end
            return result


def yearly_cost(contract):
    """Kosten pro Jahr aus Beitrag und Zahlweise."""
    return round(contract.amount * PAYMENTS_PER_YEAR[contract.interval], 2)
