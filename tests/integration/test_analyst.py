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

    @pytest.mark.parametrize('name, temperature', [
        ('gpt-4o-mini', 0.2), ('gpt-4.1', 0.2), ('gpt-6.1-sol', None), ('gpt-5.5', None), ('o3', None)])
    def test_temperature_only_for_models_that_accept_it(self, user, depot, monkeypatch, name, temperature):
        """GPT-5 und neuer lehnen eine eigene Temperatur ab; dann wird sie gar nicht erst geschickt"""
        monkeypatch.setenv('ANALYST_MODEL', name)
        client = model(('position', 'hold', 'mittel'), ('position', 'hold', 'mittel'), ('watchlist', 'wait', 'mittel'))

        service.analyse_user(user, client, today=SUNDAY)

        assert client.beta.chat.completions.parse.call_args.kwargs.get('temperature') == temperature

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


class TestTrackRecord:
    """Trefferquote aus gespeicherten Schlusskursen 30 und 90 Tage nach der Einschätzung"""

    def setup_prices(self, symbol, prices):
        """prices: {Tag: Kurs}"""
        asset = Asset.query.filter_by(symbol=symbol).first()
        if not asset:
            asset = Asset(name=symbol, symbol=symbol, currency='EUR', asset_type='etf')
            db.session.add(asset)
            db.session.commit()
        db.session.add_all([PriceHistory(asset_id=asset.id, date=datetime.combine(day, datetime.min.time()),
                                         price=price, currency='EUR') for day, price in prices.items()])
        db.session.commit()
        return asset

    def signal(self, user, asset, stance, price=100.0, day=date(2026, 6, 1)):
        db.session.add(AnalystSignal(user_id=user.id, asset_id=asset.id, run_date=day, kind='position', stance=stance,
                                     confidence='mittel', reasoning='r', invalidation='i', price=price))
        db.session.commit()

    def test_hits_by_direction_with_benchmark(self, user):
        from fintrack.analyst.track_record import track_record
        start = date(2026, 6, 1)
        up = self.setup_prices('UP.DE', {start + timedelta(days=30): 110.0, start + timedelta(days=90): 120.0})
        down = self.setup_prices('DOWN.DE', {start + timedelta(days=30): 90.0, start + timedelta(days=90): 80.0})
        flat = self.setup_prices('FLAT.DE', {start + timedelta(days=30): 101.0, start + timedelta(days=90): 99.0})
        self.setup_prices('EUNL.DE', {start: 50.0, start + timedelta(days=30): 51.0, start + timedelta(days=90): 52.0})
        self.signal(user, up, 'add')            # Kaufen, gestiegen: Treffer
        self.signal(user, down, 'review_sale')  # Verkaufen, gefallen: Treffer
        self.signal(user, flat, 'entry')        # Kaufen, nach 90 Tagen gefallen: nach 30 Treffer, nach 90 nicht
        held = self.setup_prices('HOLD.DE', {start + timedelta(days=30): 105.0, start + timedelta(days=90): 95.0})
        self.signal(user, held, 'hold')         # Halten: keine Richtung, zählt nicht zur Trefferquote

        record = track_record(user.id, today=date(2026, 9, 15))

        thirty, ninety = record['horizons']['30'], record['horizons']['90']
        assert (thirty['evaluated'], thirty['scored'], thirty['hits'], thirty['hit_rate']) == (4, 3, 3, 100)
        assert (ninety['scored'], ninety['hits'], ninety['hit_rate']) == (3, 2, 67)
        assert thirty['avg_benchmark'] == 2.0  # 50 -> 51
        stances = {s['stance']: s for s in record['by_stance']}
        assert stances['hold']['direction'] is None and stances['hold']['horizons']['30']['hit_rate'] is None
        assert stances['entry']['horizons']['90']['hit_rate'] == 0
        assert [s['stance_label'] for s in record['by_stance']] == ['Nachkaufen', 'Halten', 'Verkauf prüfen', 'Einstieg interessant']

    def test_too_young_signals_wait(self, user, login_client):
        asset = self.setup_prices('NEW.DE', {})
        self.signal(user, asset, 'add', day=date(2026, 11, 15))

        record = login_client('a@test.com').get('/api/v1/me/analyst/track-record').get_json()

        assert record['signals'] == 1
        assert record['first_result_on'] == '2026-12-15'
        assert record['horizons']['30']['evaluated'] == 0 and record['horizons']['30']['hit_rate'] is None


class TestChangePush:

    @pytest.fixture
    def push(self, user, monkeypatch):
        from fintrack.models import PushSubscription
        from fintrack.push import service as push_service
        public, private = push_service.generate_vapid_keys()
        monkeypatch.setenv('VAPID_PUBLIC_KEY', public)
        monkeypatch.setenv('VAPID_PRIVATE_KEY', private)
        delivered = []
        monkeypatch.setattr(push_service, '_deliver', lambda sub, payload, key: delivered.append(payload) or 201)
        db.session.add(PushSubscription(user_id=user.id, endpoint='https://push.example.com/1', p256dh='B', auth='a'))
        db.session.commit()
        return delivered

    def at_hour(self, monkeypatch, hour):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 15, hour, 0, tzinfo=tz)
        monkeypatch.setattr(service, 'datetime', Clock)

    def test_change_to_last_week_is_pushed_once_without_names(self, user, depot, push, monkeypatch):
        big, small, watched = depot
        self.at_hour(monkeypatch, 18)
        db.session.add(AnalystSignal(user_id=user.id, asset_id=big.id, run_date=SUNDAY - timedelta(days=7), kind='position',
                                     stance='add', confidence='mittel', reasoning='r', invalidation='i', price=200))
        db.session.commit()

        summary = service.analyse_user(user, model(('position', 'hold', 'mittel'), ('position', 'add', 'mittel'),
                                                   ('watchlist', 'wait', 'mittel')), today=SUNDAY)

        assert summary['changed'] == 1 and summary['pushed'] == 1
        assert push == [{'title': 'Neue Einschätzungen vom Analysten', 'body': 'Bei einem Wert hat sich die Einschätzung geändert.',
                         'url': '/app/analyse', 'tag': 'analyst'}]

    def test_first_run_and_unchanged_stay_quiet(self, user, depot, push, monkeypatch):
        self.at_hour(monkeypatch, 18)

        summary = service.analyse_user(user, model(('position', 'hold', 'mittel'), ('position', 'add', 'mittel'),
                                                   ('watchlist', 'wait', 'mittel')), today=SUNDAY)

        assert 'changed' not in summary and push == []

    def test_no_push_in_quiet_hours(self, user, depot, push, monkeypatch):
        big, small, watched = depot
        self.at_hour(monkeypatch, 23)
        db.session.add(AnalystSignal(user_id=user.id, asset_id=big.id, run_date=SUNDAY - timedelta(days=7), kind='position',
                                     stance='add', confidence='mittel', reasoning='r', invalidation='i', price=200))
        db.session.commit()

        summary = service.analyse_user(user, model(('position', 'hold', 'mittel'), ('position', 'add', 'mittel'),
                                                   ('watchlist', 'wait', 'mittel')), today=SUNDAY)

        assert summary['changed'] == 1 and summary['pushed'] == 0 and push == []


def test_weekly_run_creates_the_benchmark(user, fake_yahoo):
    """Ohne Vergleichsindex hätte die Trefferquote keinen MSCI-World-Vergleich"""
    fake_yahoo.add_stock('EUNL.DE', asset_type='etf')

    service.analyse_all_users(model(), today=SUNDAY)

    assert Asset.query.filter_by(symbol='EUNL.DE').count() == 1
