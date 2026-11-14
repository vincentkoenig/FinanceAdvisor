"""
test_depot_news.py - News zu den Depotpositionen im Tages-Update (insights/news.py):
Suche pro Position, Filter der Treffer, Auswertung durch die KI (nur gefundene
Quellen), Speichern am Tages-Update, API, Push-Text und Export. Tavily und OpenAI
sind ersetzt.
"""

import sys
import os
import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.insights import news
from fintrack.insights.service import generate_insight_for_user
from fintrack.models import Asset, DailyInsight, PriceHistory, UserAsset

TODAY = date(2026, 11, 13)


def article(title, url=None, date_text='Fri, 13 Nov 2026 11:00:00 GMT', content='Text'):
    return {'url': url or f'https://www.google.com/url?q={abs(hash(title))}', 'title': title,
            'content': content, 'published_date': date_text}


@pytest.fixture
def searches(monkeypatch):
    """Tavily-Schlüssel gesetzt, Suchergebnisse pro Suchbegriff aus einem dict."""
    monkeypatch.setenv('TAVILY_API_KEY', 'test')
    results = {}
    asked = []

    def search(query):
        asked.append(query)
        if results.get(query) == 'fehler':
            raise RuntimeError('Zeitüberschreitung')
        return results.get(query, [])

    monkeypatch.setattr(news, '_search', search)
    return SimpleNamespace(results=results, asked=asked)


def ai(*items):
    """OpenAI-Attrappe: parse() liefert die angegebenen Einträge, create() einen Tagestext."""
    client = MagicMock()
    client.beta.chat.completions.parse.return_value.choices = [
        MagicMock(message=MagicMock(parsed=news._Answer(items=[news._Item(**item) for item in items])))]
    client.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content='Ruhiger Tag.'))]
    return client


def position(user, name, symbol, quantity, price, asset_type='stock'):
    asset = Asset(name=name, symbol=symbol, currency='EUR', asset_type=asset_type)
    db.session.add(asset)
    db.session.commit()
    db.session.add_all([
        UserAsset(user_id=user.id, asset_id=asset.id, quantity=quantity, avg_buy_price=price, status='owned'),
        PriceHistory(asset_id=asset.id, date=datetime(2026, 11, 12), price=price, currency='EUR'),
    ])
    db.session.commit()
    return asset


@pytest.fixture
def user(make_user):
    return make_user('a@test.com')


class TestCollect:

    def test_relevant_news_with_found_sources(self, user, searches):
        sap = position(user, 'SAP SE', 'SAP.DE', 10, 200)
        searches.results['SAP SE Aktie News'] = [
            article('SAP hebt Jahresprognose an'),
            article('SAP-Aktie im Plus'),
            article('Profil', url='https://tavily.com/knowledge/company/1'),
            article('Ohne Datum', date_text=None),
        ]
        client = ai({'asset_id': sap.id, 'summary': 'SAP hat die Jahresprognose angehoben.', 'sources': [1, 1, 99]})

        result = news.collect_depot_news(user.id, client, today=TODAY)

        assert result == [{'asset_id': sap.id, 'name': 'SAP SE', 'symbol': 'SAP.DE',
                           'summary': 'SAP hat die Jahresprognose angehoben.',
                           'sources': [{'title': 'SAP hebt Jahresprognose an',
                                        'url': searches.results['SAP SE Aktie News'][0]['url']}]}]
        prompt = client.beta.chat.completions.parse.call_args.kwargs['messages'][1]['content']
        assert '[1] SAP hebt Jahresprognose an' in prompt and '[2] SAP-Aktie im Plus' in prompt
        assert 'Profil' not in prompt and 'Ohne Datum' not in prompt
        assert '10' not in prompt  # keine Stückzahlen oder Beträge an die KI

    def test_quiet_day_gives_no_news(self, user, searches):
        sap = position(user, 'SAP SE', 'SAP.DE', 10, 200)
        searches.results['SAP SE Aktie News'] = [article('SAP-Aktie im Plus')]

        assert news.collect_depot_news(user.id, ai(), today=TODAY) == []

    def test_sources_of_another_position_are_ignored(self, user, searches):
        sap = position(user, 'SAP SE', 'SAP.DE', 10, 200)
        position(user, 'Tesla', 'TSLA', 10, 300)
        searches.results['SAP SE Aktie News'] = [article('SAP: Übernahme')]
        searches.results['Tesla Aktie News'] = [article('Tesla: Rückruf')]
        # Die Tesla-Position ist wertvoller (3.000 € gegen 2.000 €) und kommt zuerst: Nummer 1 ist der Rückruf
        client = ai({'asset_id': sap.id, 'summary': 'Erfundene Zuordnung.', 'sources': [1]})

        assert news.collect_depot_news(user.id, client, today=TODAY) == []

    def test_largest_positions_first_and_capped(self, user, searches, monkeypatch):
        monkeypatch.setattr(news, 'MAX_POSITIONS', 2)
        position(user, 'Klein', 'K.DE', 1, 10)
        position(user, 'Groß', 'G.DE', 100, 10)
        position(user, 'Mittel', 'M.DE', 10, 10, asset_type='etf')

        news.collect_depot_news(user.id, ai(), today=TODAY)

        assert searches.asked == ['Groß Aktie News', 'Mittel ETF News']

    def test_failed_search_skips_only_that_position(self, user, searches):
        position(user, 'Tesla', 'TSLA', 10, 300)
        sap = position(user, 'SAP SE', 'SAP.DE', 1, 200)
        searches.results['Tesla Aktie News'] = 'fehler'
        searches.results['SAP SE Aktie News'] = [article('SAP: Übernahme')]
        client = ai({'asset_id': sap.id, 'summary': 'SAP übernimmt eine Firma.', 'sources': [1]})

        assert [n['name'] for n in news.collect_depot_news(user.id, client, today=TODAY)] == ['SAP SE']

    def test_without_key_nothing_is_searched(self, user, monkeypatch):
        monkeypatch.delenv('TAVILY_API_KEY', raising=False)
        position(user, 'SAP SE', 'SAP.DE', 10, 200)
        client = ai()

        assert news.collect_depot_news(user.id, client, today=TODAY) == []
        client.beta.chat.completions.parse.assert_not_called()

    def test_no_articles_means_no_ai_call(self, user, searches):
        position(user, 'SAP SE', 'SAP.DE', 10, 200)
        client = ai()

        assert news.collect_depot_news(user.id, client, today=TODAY) == []
        client.beta.chat.completions.parse.assert_not_called()


class TestDailyUpdate:

    def test_news_are_stored_and_served(self, user, searches, login_client):
        sap = position(user, 'SAP SE', 'SAP.DE', 10, 200)
        searches.results['SAP SE Aktie News'] = [article('SAP hebt Prognose an')]
        client = ai({'asset_id': sap.id, 'summary': 'SAP hebt die Prognose an.', 'sources': [1]})

        assert generate_insight_for_user(user.id, client)

        data = login_client('a@test.com').get('/api/v1/me/insight').get_json()
        assert data['content'] == 'Ruhiger Tag.'
        assert [n['summary'] for n in data['news']] == ['SAP hebt die Prognose an.']

    def test_news_failure_keeps_the_update(self, user, searches, monkeypatch):
        position(user, 'SAP SE', 'SAP.DE', 10, 200)
        searches.results['SAP SE Aktie News'] = [article('SAP hebt Prognose an')]
        client = ai()
        client.beta.chat.completions.parse.side_effect = RuntimeError('OpenAI nicht erreichbar')

        assert generate_insight_for_user(user.id, client)
        insight = DailyInsight.query.one()
        assert insight.content == 'Ruhiger Tag.' and insight.news is None

    def test_old_insight_without_news(self, user, login_client):
        db.session.add(DailyInsight(user_id=user.id, content='Alt.', created_at=datetime(2026, 11, 1, 22, 30)))
        db.session.commit()

        assert login_client('a@test.com').get('/api/v1/me/insight').get_json()['news'] == []


class TestPushAndExport:

    def test_push_mentions_only_the_count(self, user, monkeypatch):
        from fintrack.models import PushSubscription
        from fintrack.push import notify, service
        public, private = service.generate_vapid_keys()
        monkeypatch.setenv('VAPID_PUBLIC_KEY', public)
        monkeypatch.setenv('VAPID_PRIVATE_KEY', private)
        delivered = []
        monkeypatch.setattr(service, '_deliver', lambda sub, payload, key: delivered.append(payload) or 201)
        db.session.add(PushSubscription(user_id=user.id, endpoint='https://push.example.com/1', p256dh='B', auth='a'))
        stored = [{'asset_id': 1, 'name': 'SAP SE', 'symbol': 'SAP.DE', 'summary': 'x', 'sources': []},
                  {'asset_id': 2, 'name': 'Tesla', 'symbol': 'TSLA', 'summary': 'y', 'sources': []}]
        db.session.add(DailyInsight(user_id=user.id, content='Text', created_at=datetime(2026, 11, 13, 22, 30),
                                    news=json.dumps(stored)))
        db.session.commit()

        notify.notify_daily_update(user.id, datetime(2026, 11, 14, 8, 0))

        assert delivered[0]['body'] == 'Mit News zu 2 Werten aus deinem Depot.'
        assert 'SAP' not in delivered[0]['body'] and 'Tesla' not in delivered[0]['body']

    def test_export_and_import_keep_news(self, make_user, login_client):
        first = make_user('a@test.com')
        stored = [{'asset_id': 1, 'name': 'SAP SE', 'symbol': 'SAP.DE', 'summary': 'x',
                   'sources': [{'title': 'T', 'url': 'https://example.com/a'}]}]
        db.session.add(DailyInsight(user_id=first.id, content='Text', created_at=datetime(2026, 11, 13, 22, 30),
                                    news=json.dumps(stored)))
        db.session.commit()
        exported = login_client('a@test.com').get('/api/v1/me/export').get_json()
        assert exported['insights'][0]['news'] == stored

        make_user('b@test.com')
        assert login_client('b@test.com').post('/api/v1/me/import', json=exported).status_code == 201
        second = DailyInsight.query.filter(DailyInsight.user_id != first.id).one()
        assert json.loads(second.news) == stored
