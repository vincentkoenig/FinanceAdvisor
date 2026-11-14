"""
insights/news.py - News zu den eigenen Depotpositionen für das Tages-Update.

Ablauf (abends mit dem Tages-Update, insights/service.py):
1. Für jede Position (höchstens MAX_POSITIONS, die wertvollsten zuerst) sucht Tavily
   nach News der letzten 24 Stunden. Tavily bekommt nur Name des Werts, keine Beträge.
2. gpt-4o-mini liest die Treffer und behält nur Kursrelevantes (Zahlen, Prognose,
   Übernahme, Klage, Chefwechsel ...), als einen Satz auf Deutsch pro Wert, mit den
   Nummern der Artikel als Quellen. Ruhige Tage ergeben eine leere Liste.
3. Quellen nimmt FinTrack nur aus den gefundenen Artikeln, nie Links, die sich die KI
   ausdenkt. Tavily liefert News-Links oft als Google-Weiterleitung; die führt zum
   Artikel, verrät aber die Domain nicht. Angezeigt wird deshalb die Schlagzeile.

Kosten: eine Tavily-Suche pro Position und Tag (kostenlos bis etwa 1.000 im Monat),
dazu ein kurzer gpt-4o-mini-Aufruf.
"""

import logging
import os
from typing import List

from pydantic import BaseModel

from fintrack.contracts.terms import today_berlin
from fintrack.extensions import db
from fintrack.market.service import price_in_eur_on
from fintrack.models import Asset, UserAsset

logger = logging.getLogger(__name__)

MAX_POSITIONS = 20
RESULTS_PER_POSITION = 3
CONTENT_CHARS = 500
# Treffer dieser Domains sind keine Artikel (z.B. Firmenprofile von Tavily selbst)
SKIP_DOMAINS = ('tavily.com',)

INSTRUCTIONS = """Du filterst Nachrichten zu Wertpapieren für eine private Finanz-App.
Du bekommst pro Wertpapier einige Artikel der letzten 24 Stunden mit Nummer in eckigen Klammern.

Behalte nur Ereignisse, die den Kurs des Wertpapiers bewegen können:
Quartals- oder Jahreszahlen, Prognosen, Übernahmen und Fusionen, Klagen, Strafen oder Regulierung,
Wechsel im Vorstand, Dividenden oder Aktienrückkäufe, große Aufträge, Rückrufe, bei ETFs Änderungen
am Fonds selbst, bei Kryptowährungen Ereignisse am Netzwerk oder große Regulierungsschritte.

Lass weg: bloße Kursbewegungen ("Aktie im Plus"), Chartanalysen, Analystenkommentare und Kursziele,
allgemeine Marktberichte, Werbung, Artikel, die gar nicht von diesem Wertpapier handeln.

Für jedes Wertpapier mit mindestens einem solchen Ereignis: genau ein sachlicher Satz auf Deutsch
(höchstens 30 Wörter), was passiert ist, und die Nummern der Artikel, auf die er sich stützt.
Keine Kauf- oder Verkaufsempfehlung, keine Vermutungen. Wertpapiere ohne solches Ereignis lässt du weg.
Ist an diesem Tag nichts Relevantes dabei, gib eine leere Liste zurück."""


class _Item(BaseModel):
    asset_id: int
    summary: str
    sources: List[int]


class _Answer(BaseModel):
    items: List[_Item]


def _positions(user_id, today):
    """Positionen mit Menge > 0, die wertvollsten zuerst (letzter Schlusskurs, sonst Kaufpreis)."""
    rows = db.session.query(UserAsset, Asset).join(Asset, Asset.id == UserAsset.asset_id) \
        .filter(UserAsset.user_id == user_id, UserAsset.quantity > 0).all()

    def value(row):
        position, asset = row
        price = price_in_eur_on(asset, today) or position.avg_buy_price or 0
        return position.quantity * price

    return [asset for _, asset in sorted(rows, key=value, reverse=True)][:MAX_POSITIONS]


def _query(asset):
    kinds = {'etf': 'ETF', 'crypto': 'Kryptowährung', 'metal': 'Preis'}
    return f'{asset.name} {kinds.get(asset.asset_type, "Aktie")} News'


def _search(query):
    """News der letzten 24 Stunden bei Tavily als Liste von Treffern (url, title, content, published_date)."""
    from langchain_tavily import TavilySearch

    search = TavilySearch(max_results=RESULTS_PER_POSITION + 2, topic='news', time_range='day',
                          api_key=os.getenv('TAVILY_API_KEY'))
    return search.invoke({'query': query}).get('results') or []


def _articles(results):
    """Nur echte, datierte Artikel; Inhalt gekürzt."""
    articles = []
    for result in results:
        url, title = result.get('url') or '', (result.get('title') or '').strip()
        if not url.startswith('https://') or not title or not result.get('published_date'):
            continue
        if any(domain in url for domain in SKIP_DOMAINS):
            continue
        articles.append({'url': url, 'title': title[:200],
                         'content': ' '.join((result.get('content') or '').split())[:CONTENT_CHARS]})
        if len(articles) == RESULTS_PER_POSITION:
            break
    return articles


def _ask(openai_client, found):
    """found: Liste von (Asset, Artikel). Artikel bekommen fortlaufende Nummern."""
    lines, numbered = [], {}
    for asset, articles in found:
        lines.append(f'\nWertpapier {asset.id}: {asset.name} ({asset.symbol})')
        for article in articles:
            number = len(numbered) + 1
            numbered[number] = (asset.id, article)
            lines.append(f'[{number}] {article["title"]} - {article["content"]}')
    response = openai_client.beta.chat.completions.parse(
        model='gpt-4o-mini',
        messages=[{'role': 'system', 'content': INSTRUCTIONS},
                  {'role': 'user', 'content': '\n'.join(lines)}],
        temperature=0,
        response_format=_Answer,
    )
    return response.choices[0].message.parsed.items, numbered


def collect_depot_news(user_id, openai_client, today=None):
    """
    News zu den Depotpositionen als Liste von
    {asset_id, name, symbol, summary, sources: [{title, url}]}, leer an ruhigen Tagen.
    Ohne Tavily-Schlüssel oder ohne Positionen gibt es keine News.
    """
    if not os.getenv('TAVILY_API_KEY'):
        return []
    today = today or today_berlin()
    found = []
    for asset in _positions(user_id, today):
        try:
            articles = _articles(_search(_query(asset)))
        except Exception as error:
            logger.warning('News-Suche für %s fehlgeschlagen: %s', asset.symbol, error)
            continue
        if articles:
            found.append((asset, articles))
    if not found:
        return []

    items, numbered = _ask(openai_client, found)
    assets = {asset.id: asset for asset, _ in found}
    news = []
    for item in items:
        asset = assets.get(item.asset_id)
        summary = ' '.join(item.summary.split())[:300]
        # Nur Quellen, die zu diesem Wert gefunden wurden
        sources = [numbered[n][1] for n in dict.fromkeys(item.sources)
                   if n in numbered and numbered[n][0] == item.asset_id]
        if not asset or not summary or not sources or any(n['asset_id'] == asset.id for n in news):
            continue
        news.append({'asset_id': asset.id, 'name': asset.name, 'symbol': asset.symbol, 'summary': summary,
                     'sources': [{'title': s['title'], 'url': s['url']} for s in sources]})
    return news
