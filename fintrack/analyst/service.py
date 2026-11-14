"""
analyst/service.py - Der wöchentliche Analyst (Sonntag 18 Uhr, jobs.py): eine Einschätzung
pro Depotposition und Watchlist-Wert nach dem Ansatz "Trend + Rücksetzer".

Pro Wert:
1. Kennzahlen aus der gespeicherten Kurshistorie (analyst/indicators.py), rein gerechnet
2. News der letzten Woche bei Tavily (nur der Name des Werts geht raus)
3. Das Modell (ANALYST_MODEL) wählt eine der erlaubten Stufen, mit Zuversicht, kurzer
   Begründung und der Kursmarke, ab der die Einschätzung nicht mehr gilt. Es bekommt
   Kennzahlen, News, das Risikoprofil und das Gewicht der Position in Prozent,
   keine Euro-Beträge oder Stückzahlen.

Gespeichert wird jede Einschätzung mit dem Kurs vom Lauf (AnalystSignal), damit sich
später messen lässt, wie gut der Analyst lag. Er handelt nie selbst, und seine
Einschätzungen sind automatisch erzeugt, keine Anlageberatung.
"""

import json
import logging
import os
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from fintrack.analyst import indicators as ind
from fintrack.contracts.terms import today_berlin
from fintrack.extensions import db
from fintrack.insights import news
from fintrack.market.service import price_history_in_eur
from fintrack.models import AnalystSignal, Asset, User, UserAsset, Watchlist

logger = logging.getLogger(__name__)

# Bis ein stärkeres Modell auf dem Server eingetragen ist, das schon genutzte günstige
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_ASSETS = 30
NEWS_PER_ASSET = 3
# Ist der letzte gespeicherte Kurs älter (z.B. weil der Kurs-Lauf ausgefallen ist), wird nicht eingeschätzt
MAX_PRICE_AGE_DAYS = 7

POSITION_STANCES = ('add', 'hold', 'take_profit', 'review_sale')
WATCHLIST_STANCES = ('entry', 'wait', 'avoid')
STANCE_LABELS = {
    'add': 'Nachkaufen', 'hold': 'Halten', 'take_profit': 'Teilgewinn mitnehmen', 'review_sale': 'Verkauf prüfen',
    'entry': 'Einstieg interessant', 'wait': 'Abwarten', 'avoid': 'Meiden',
}
RISK_LABELS = {'conservative': 'konservativ', 'balanced': 'ausgewogen', 'aggressive': 'risikofreudig'}
HORIZON_LABELS = {'short-term': 'kurzfristig', 'medium-term': 'mittelfristig', 'long-term': 'langfristig'}

INSTRUCTIONS = """Du bist der wöchentliche Analyst einer privaten Finanz-App und schätzt ein einzelnes
Wertpapier nach dem Ansatz "Trend + Rücksetzer" ein:
- Der langfristige Trend (200-Tage-Linie und ihre Richtung) bestimmt die Grundrichtung.
- Einstiege oder Nachkäufe bevorzugt nach Rücksetzern in einem intakten Aufwärtstrend
  (deutlich unter dem Jahreshoch oder RSI unter 40), nicht nach starken Anstiegen.
- Bei Überhitzung (RSI über 75 und weit über der 200-Tage-Linie) kann ein Teilgewinn sinnvoll sein.
- Fällt der Kurs nachhaltig unter eine fallende 200-Tage-Linie, ist der Trend gebrochen: prüfen,
  ob verkauft oder abgesichert werden sollte.
- Wichtige Nachrichten können die Einschätzung verstärken oder abschwächen. Das Risikoprofil des
  Anlegers und das Gewicht der Position im Depot fließen ein (hohes Gewicht: vorsichtiger nachkaufen).

Antworte nur mit einer der erlaubten Stufen. Zuversicht "niedrig", wenn die Signale widersprüchlich
sind oder Daten fehlen. Begründung: 2 bis 3 sachliche Sätze auf Deutsch, die sich auf die genannten
Kennzahlen und Nachrichten stützen, keine erfundenen Zahlen, keine Kursprognosen mit Zieldatum.
Ungültig-wenn: ein Satz mit einer konkreten Kursmarke in Euro, ab der die Einschätzung nicht mehr
gilt (z.B. "Schluss unter der 200-Tage-Linie bei 182 €"). Du handelst nie selbst."""


class _PositionAnswer(BaseModel):
    stance: Literal['add', 'hold', 'take_profit', 'review_sale']
    confidence: Literal['niedrig', 'mittel', 'hoch']
    reasoning: str = Field(max_length=700)
    invalidation: str = Field(max_length=300)


class _WatchlistAnswer(BaseModel):
    stance: Literal['entry', 'wait', 'avoid']
    confidence: Literal['niedrig', 'mittel', 'hoch']
    reasoning: str = Field(max_length=700)
    invalidation: str = Field(max_length=300)


def model_name():
    return os.getenv('ANALYST_MODEL') or DEFAULT_MODEL


def _candidates(user_id):
    """
    (Asset, kind, Gewicht im Depot in Prozent oder None): Positionen zuerst, nach Wert,
    dann Watchlist-Werte, die nicht im Depot liegen. Höchstens MAX_ASSETS.
    """
    rows = db.session.query(UserAsset, Asset).join(Asset, Asset.id == UserAsset.asset_id) \
        .filter(UserAsset.user_id == user_id, UserAsset.quantity > 0).all()
    values = {}
    for position, asset in rows:
        history = price_history_in_eur(asset)
        price = history[-1][1] if history else (position.avg_buy_price or 0)
        values[asset.id] = (asset, position.quantity * price)
    total = sum(value for _, value in values.values()) or 1
    result = [(asset, 'position', round(value / total * 100, 1))
              for asset, value in sorted(values.values(), key=lambda item: item[1], reverse=True)]

    watched = db.session.query(Watchlist, Asset).join(Asset, Asset.id == Watchlist.asset_id) \
        .filter(Watchlist.user_id == user_id).order_by(Watchlist.id).all()
    result += [(asset, 'watchlist', None) for _, asset in watched if asset.id not in values]
    return result[:MAX_ASSETS]


def _week_news(asset):
    """Bis zu NEWS_PER_ASSET Schlagzeilen der letzten Woche, oder [] ohne Tavily."""
    if not os.getenv('TAVILY_API_KEY'):
        return []
    try:
        return news._articles(news._search(news._query(asset), time_range='week'))[:NEWS_PER_ASSET]
    except Exception as error:
        logger.warning('Wochen-News für %s nicht verfügbar: %s', asset.symbol, error)
        return []


def _fmt(value, suffix=''):
    return 'unbekannt' if value is None else f'{value}{suffix}'


def _prompt(asset, kind, weight, values, signals, articles, user):
    stances = POSITION_STANCES if kind == 'position' else WATCHLIST_STANCES
    trend = {'up': 'aufwärts', 'down': 'abwärts', 'sideways': 'seitwärts', None: 'unbekannt (zu wenig Historie)'}
    lines = [
        f'Wertpapier: {asset.name} ({asset.symbol}), Art: {asset.asset_type or "unbekannt"}',
        'Im Depot, Anteil am Depot: ' + _fmt(weight, ' %') if kind == 'position' else 'Auf der Watchlist (nicht im Depot)',
        f'Erlaubte Stufen: {", ".join(f"{s} ({STANCE_LABELS[s]})" for s in stances)}',
        f'Risikoprofil: {RISK_LABELS.get(user.risk_profile, "nicht angegeben")}, '
        f'Anlagehorizont: {HORIZON_LABELS.get(user.investment_horizon, "nicht angegeben")}',
        '',
        f'Kennzahlen (Stand {values["as_of"]}, Kurse in Euro):',
        f'- Kurs: {values["price"]}, 50-Tage-Linie: {_fmt(values["sma50"])}, 200-Tage-Linie: {_fmt(values["sma200"])}'
        f' ({"steigend" if values["sma200_rising"] else "fallend" if values["sma200_rising"] is False else "Richtung unbekannt"})',
        f'- Abstand zur 200-Tage-Linie: {_fmt(values["above_sma200_pct"], " %")}, RSI 14: {_fmt(values["rsi14"])}',
        f'- Jahreshoch: {values["high_52w"]}, Abstand: {values["from_high_pct"]} %',
        f'- Entwicklung 1 / 3 / 12 Monate: {_fmt(values["change_1m_pct"], " %")} / {_fmt(values["change_3m_pct"], " %")}'
        f' / {_fmt(values["change_12m_pct"], " %")}, Schwankung (annualisiert): {_fmt(values["volatility_pct"], " %")}',
        f'- Einordnung: Trend {trend[signals["trend"]]}'
        + (', Rücksetzer im Aufwärtstrend' if signals['pullback'] else '')
        + (', überhitzt' if signals['overheated'] else '')
        + (', Trendbruch' if signals['trend_break'] else ''),
        '',
        'Nachrichten der letzten Woche:' if articles else 'Keine Nachrichten der letzten Woche gefunden.',
    ]
    lines += [f'- {a["title"]}: {a["content"]}' for a in articles]
    return '\n'.join(lines)


def _ask(openai_client, prompt, kind):
    response = openai_client.beta.chat.completions.parse(
        model=model_name(),
        messages=[{'role': 'system', 'content': INSTRUCTIONS}, {'role': 'user', 'content': prompt}],
        temperature=0.2,
        response_format=_PositionAnswer if kind == 'position' else _WatchlistAnswer,
    )
    return response.choices[0].message.parsed


def analyse_user(user, openai_client, today=None):
    """Einschätzungen für einen Nutzer. Ein Wert pro Lauf und Tag; schon eingeschätzte werden übersprungen."""
    today = today or today_berlin()
    summary = {'signals': 0, 'skipped': 0, 'errors': []}
    done = {row.asset_id for row in AnalystSignal.query.filter_by(user_id=user.id, run_date=today)}
    for asset, kind, weight in _candidates(user.id):
        if asset.id in done:
            continue
        values = ind.compute(price_history_in_eur(asset))
        if not values or (today - date.fromisoformat(values['as_of'])).days > MAX_PRICE_AGE_DAYS:
            summary['skipped'] += 1
            continue
        signals = ind.classify(values)
        try:
            answer = _ask(openai_client, _prompt(asset, kind, weight, values, signals, _week_news(asset), user), kind)
        except Exception as error:
            logger.exception('Einschätzung für %s fehlgeschlagen', asset.symbol)
            summary['errors'].append(f'{asset.symbol}: {error}')
            continue
        db.session.add(AnalystSignal(
            user_id=user.id, asset_id=asset.id, run_date=today, kind=kind, stance=answer.stance,
            confidence=answer.confidence, reasoning=' '.join(answer.reasoning.split()),
            invalidation=' '.join(answer.invalidation.split()), price=values['price'],
            indicators=json.dumps({**values, **signals}), model=model_name()))
        db.session.commit()
        summary['signals'] += 1
    return summary


def analyse_all_users(openai_client, today=None):
    """Wöchentlicher Lauf für alle Nutzer (FinTrack hat derzeit einen)."""
    result = {}
    for user in User.query.order_by(User.id).all():
        result[user.id] = analyse_user(user, openai_client, today)
    return result
