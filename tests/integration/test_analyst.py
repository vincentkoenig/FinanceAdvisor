"""
test_analyst.py - Wöchentlicher Analyst (analyst/service.py, analyst/routes.py): welche
Werte eingeschätzt werden, was an das Modell geht (keine Beträge), Speichern, die
Anzeige mit Änderung zur Vorwoche und der Export. Das Modell und Tavily sind ersetzt.
"""

import sys
import os
import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.analyst import service
from fintrack.extensions import db
from fintrack.models import AnalystSignal, Asset, PriceHistory, UserAsset, Watchlist

SUNDAY = date(2026, 11, 15)


def model(*answers):
    """Modell-Attrappe: gibt die Antworten der Reihe nach zurück und merkt sich die Prompts."""
    client = MagicMock()
    parsed = []
    for kind, stance, confidence in answers:
        cls = service._PositionAnswer if kind == 'position' else service._WatchlistAnswer
        parsed.append(cls(stance=stance, confidence=confidence, reasoning='Trend intakt, Rücksetzer.',
                          invalidation='Schluss unter 180 €.'))
    client.beta.chat.completions.parse.side_effect = [MagicMock(choices=[MagicMock(message=MagicMock(parsed=p))])
                                                      for p in parsed]
    return client


def asset_with_history(symbol, name, days=260, start=100.0, step=0.5):
    asset = Asset(name=name, symbol=symbol, currency='EUR', asset_type='stock')
    db.session.add(asset)
    db.session.commit()
    first = SUNDAY - timedelta(days=days)
    db.session.add_all([PriceHistory(asset_id=asset.id, date=datetime.combine(first + timedelta(days=i), datetime.min.time()),
                                     price=start + i * step, currency='EUR') for i in range(days)])
    db.session.commit()
    return asset


@pytest.fixture
def user(make_user):
    user = make_user('a@test.com')
    user.risk_profile = 'balanced'
    db.session.commit()
    return user


@pytest.fixture
def depot(user):
    big = asset_with_history('SAP.DE', 'SAP SE')
    small = asset_with_history('TSLA', 'Tesla', start=50.0)
    watched = asset_with_history('NVD.DE', 'NVIDIA')
    db.session.add_all([
        UserAsset(user_id=user.id, asset_id=small.id, quantity=1, avg_buy_price=50, status='owned'),
        UserAsset(user_id=user.id, asset_id=big.id, quantity=10, avg_buy_price=100, status='owned'),
        Watchlist(user_id=user.id, asset_id=watched.id, price_added=200),
        Watchlist(user_id=user.id, asset_id=big.id, price_added=200),  # schon im Depot: nur einmal
    ])
    db.session.commit()
    return big, small, watched


class TestRun:

    def test_positions_first_then_watchlist(self, user, depot):
        big, small, watched = depot
        client = model(('position', 'hold', 'mittel'), ('position', 'add', 'niedrig'), ('watchlist', 'entry', 'hoch'))

        summary = service.analyse_user(user, client, today=SUNDAY)

        assert summary == {'signals': 3, 'skipped': 0, 'errors': []}
        stored = AnalystSignal.query.order_by(AnalystSignal.id).all()
        assert [(s.asset_id, s.kind, s.stance) for s in stored] == [
            (big.id, 'position', 'hold'), (small.id, 'position', 'add'), (watched.id, 'watchlist', 'entry')]
        assert stored[0].price == pytest.approx(100 + 259 * 0.5)
        assert json.loads(stored[0].indicators)['trend'] == 'up'
        assert stored[0].model == 'gpt-4o-mini'

    def test_prompt_has_no_amounts_and_only_allowed_stances(self, user, depot):
        client = model(('position', 'hold', 'mittel'), ('position', 'hold', 'mittel'), ('watchlist', 'wait', 'mittel'))

        service.analyse_user(user, client, today=SUNDAY)

        calls = client.beta.chat.completions.parse.call_args_list
        first = calls[0].kwargs['messages'][1]['content']
        assert 'Anteil am Depot: ' in first and 'Risikoprofil: ausgewogen' in first
        assert 'add (Nachkaufen)' in first and 'entry' not in first
        assert 'Stück' not in first and 'avg' not in first
        assert calls[0].kwargs['response_format'] is service._PositionAnswer
        assert calls[2].kwargs['response_format'] is service._WatchlistAnswer
        assert 'Auf der Watchlist' in calls[2].kwargs['messages'][1]['content']

    def test_model_from_setting(self, user, depot, monkeypatch):
        monkeypatch.setenv('ANALYST_MODEL', 'starkes-modell')
        client = model(('position', 'hold', 'mittel'), ('position', 'hold', 'mittel'), ('watchlist', 'wait', 'mittel'))

        service.analyse_user(user, client, today=SUNDAY)

        assert client.beta.chat.completions.parse.call_args.kwargs['model'] == 'starkes-modell'
        assert AnalystSignal.query.first().model == 'starkes-modell'

    def test_second_run_same_day_skips_done(self, user, depot):
        service.analyse_user(user, model(('position', 'hold', 'mittel'), ('position', 'hold', 'mittel'),
                                         ('watchlist', 'wait', 'mittel')), today=SUNDAY)
        client = model()

        assert service.analyse_user(user, client, today=SUNDAY)['signals'] == 0
        client.beta.chat.completions.parse.assert_not_called()

    def test_failure_for_one_asset_keeps_the_others(self, user, depot):
        client = MagicMock()
        ok = MagicMock(choices=[MagicMock(message=MagicMock(parsed=service._PositionAnswer(
            stance='hold', confidence='mittel', reasoning='x', invalidation='y')))])
        client.beta.chat.completions.parse.side_effect = [RuntimeError('Zeitüberschreitung'), ok, RuntimeError('kaputt')]

        summary = service.analyse_user(user, client, today=SUNDAY)

        assert summary['signals'] == 1 and len(summary['errors']) == 2

    def test_asset_without_prices_is_skipped(self, user):
        asset = Asset(name='Neu', symbol='NEU.DE', currency='EUR', asset_type='stock')
        db.session.add(asset)
        db.session.commit()
        db.session.add(Watchlist(user_id=user.id, asset_id=asset.id))
        db.session.commit()

        assert service.analyse_user(user, model(), today=SUNDAY) == {'signals': 0, 'skipped': 1, 'errors': []}

    def test_stale_prices_are_skipped(self, user, depot):
        """Ist der Kurs-Lauf über eine Woche ausgefallen, urteilt der Analyst nicht mit alten Kursen"""
        client = model()

        summary = service.analyse_user(user, client, today=SUNDAY + timedelta(days=9))

        assert summary == {'signals': 0, 'skipped': 3, 'errors': []}
        client.beta.chat.completions.parse.assert_not_called()

    def test_week_news_are_passed_on(self, user, depot, monkeypatch):
        from fintrack.insights import news
        monkeypatch.setenv('TAVILY_API_KEY', 'test')
        ranges = []

        def search(query, time_range='day'):
            ranges.append(time_range)
            return [{'url': 'https://example.com/a', 'title': f'Meldung zu {query}', 'content': 'Inhalt',
                     'published_date': 'Fri, 13 Nov 2026 11:00:00 GMT'}]
        monkeypatch.setattr(news, '_search', search)
        client = model(('position', 'hold', 'mittel'), ('position', 'hold', 'mittel'), ('watchlist', 'wait', 'mittel'))

        service.analyse_user(user, client, today=SUNDAY)

        assert set(ranges) == {'week'}
        assert 'Meldung zu SAP SE Aktie News' in client.beta.chat.completions.parse.call_args_list[0].kwargs['messages'][1]['content']


class TestRoute:

    def test_latest_run_with_change_marker(self, user, depot, login_client):
        big, small, watched = depot
        last_week = SUNDAY - timedelta(days=7)
        db.session.add(AnalystSignal(user_id=user.id, asset_id=big.id, run_date=last_week, kind='position',
                                     stance='add', confidence='mittel', reasoning='r', invalidation='i', price=200))
        db.session.commit()
        service.analyse_user(user, model(('position', 'hold', 'mittel'), ('position', 'add', 'niedrig'),
                                         ('watchlist', 'entry', 'hoch')), today=SUNDAY)

        data = login_client('a@test.com').get('/api/v1/me/analyst').get_json()

        assert data['run_date'] == SUNDAY.isoformat()
        assert [(i['name'], i['kind'], i['stance_label']) for i in data['items']] == [
            ('SAP SE', 'position', 'Halten'), ('Tesla', 'position', 'Nachkaufen'), ('NVIDIA', 'watchlist', 'Einstieg interessant')]
        sap = data['items'][0]
        assert sap['changed'] is True and sap['previous_label'] == 'Nachkaufen'
        assert data['items'][1]['changed'] is False and data['items'][1]['previous_label'] is None
        assert sap['indicators']['trend'] == 'up' and 'price' not in sap['indicators']

    def test_empty(self, user, login_client):
        assert login_client('a@test.com').get('/api/v1/me/analyst').get_json()['items'] == []

    def test_needs_login(self, app):
        assert app.test_client().get('/api/v1/me/analyst').status_code == 401


class TestExport:

    def test_signals_and_watchlist_targets_survive_export_and_import(self, make_user, login_client, depot, user):
        big, small, watched = depot
        Watchlist.query.filter_by(asset_id=watched.id).one().target_price = 250
        Watchlist.query.filter_by(asset_id=watched.id).one().target_direction = 'above'
        db.session.add(AnalystSignal(user_id=user.id, asset_id=big.id, run_date=SUNDAY, kind='position', stance='hold',
                                     confidence='mittel', reasoning='r', invalidation='i', price=229.5,
                                     indicators=json.dumps({'trend': 'up'}), model='m'))
        db.session.commit()
        exported = login_client('a@test.com').get('/api/v1/me/export').get_json()
        assert exported['analyst_signals'][0]['stance'] == 'hold'

        other = make_user('b@test.com')
        assert login_client('b@test.com').post('/api/v1/me/import', json=exported).status_code == 201
        copied = AnalystSignal.query.filter_by(user_id=other.id).one()
        assert (copied.stance, copied.price, json.loads(copied.indicators)) == ('hold', 229.5, {'trend': 'up'})
        target = Watchlist.query.filter_by(user_id=other.id).filter(Watchlist.target_price.isnot(None)).one()
        assert (target.target_price, target.target_direction) == (250, 'above')
