"""
test_migration_0003.py - Tests für die Bereinigung in Migration
0003_price_data_model: Eine Datenbank im Stand davor (mit doppelten Assets,
Positionen, Watchlist-Einträgen, Dividenden und gemischter Kurshistorie)
wird migriert. Danach müssen alle Duplikate zusammengeführt sein, ohne dass
Eingaben der Nutzer verloren gehen.

Läuft gegen SQLite und - wenn TEST_POSTGRES_URL gesetzt ist - gegen PostgreSQL.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from flask_migrate import upgrade
from sqlalchemy import inspect, text

from fintrack.extensions import db

BEFORE = '0002_login_security'


def insert(table, **values):
    columns = ', '.join(f'"{c}"' for c in values)
    params = ', '.join(f':{c}' for c in values)
    with db.engine.begin() as connection:
        return connection.execute(
            text(f'INSERT INTO "{table}" ({columns}) VALUES ({params}) RETURNING id'), values).scalar()


def rows(sql, **params):
    with db.engine.connect() as connection:
        return connection.execute(text(sql), params).fetchall()


@pytest.fixture
def old_database(migration_app):
    """Datenbank im Stand 0002 mit Duplikaten wie in der August-Kopie."""
    upgrade(revision=BEFORE)

    anna = insert('user', username='anna', email='anna@test.com', password='x', verification_attempts=0)
    ben = insert('user', username='ben', email='ben@test.com', password='x', verification_attempts=0)

    # AAPL dreimal, NKE einmal
    aapl_1 = insert('asset', name='Apple Inc.', symbol='AAPL', asset_type='stock', currency='EUR')
    aapl_2 = insert('asset', name='Apple Inc.', symbol='AAPL', asset_type='stock', currency='EUR')
    aapl_3 = insert('asset', name='Apple', symbol='AAPL', asset_type='stock', currency='EUR')
    nke = insert('asset', name='NIKE, Inc.', symbol='NKE', asset_type='stock', currency='EUR')

    # Kurshistorie mit Doppel-Tagen (wird geleert)
    for asset_id in (aapl_1, aapl_2, nke):
        insert('price_history', asset_id=asset_id, date=datetime(2026, 8, 1), price=200.0, currency='EUR')
        insert('price_history', asset_id=asset_id, date=datetime(2026, 8, 1, 15, 47), price=171.0, currency='EUR')

    # Anna hält Apple über zwei der doppelten Assets: 2 Stück à 100 und 2 Stück à 200
    insert('user_asset', user_id=anna, asset_id=aapl_1, quantity=2.0, avg_buy_price=100.0,
           bought_at=datetime(2026, 3, 1), status='owned')
    insert('user_asset', user_id=anna, asset_id=aapl_3, quantity=2.0, avg_buy_price=200.0,
           bought_at=datetime(2026, 1, 1), status='owned')
    insert('user_asset', user_id=anna, asset_id=nke, quantity=1.0, avg_buy_price=50.0,
           bought_at=datetime(2026, 2, 1), status='owned')
    # Ben hält Apple nur einmal - darf nicht verändert werden
    insert('user_asset', user_id=ben, asset_id=aapl_2, quantity=5.0, avg_buy_price=150.0,
           bought_at=datetime(2026, 4, 1), status='owned')

    # Käufe, Sparplan und Watchlist hängen an verschiedenen Duplikaten
    insert('asset_transaction', user_id=anna, asset_id=aapl_1, type='buy', quantity=2.0, price=100.0,
           date=datetime(2026, 3, 1))
    insert('asset_transaction', user_id=anna, asset_id=aapl_3, type='buy', quantity=2.0, price=200.0,
           date=datetime(2026, 1, 1))
    insert('savings_plan', user_id=anna, asset_id=aapl_2, amount=50.0, day_of_month=1, active=True)
    insert('watchlist', user_id=ben, asset_id=aapl_1, price_added=170.0, added_at=datetime(2026, 5, 1))
    insert('watchlist', user_id=ben, asset_id=aapl_3, price_added=180.0, added_at=datetime(2026, 6, 1))

    # Dieselbe Dividende wurde für zwei Apple-Duplikate gebucht, jeweils mit Einnahme
    category = insert('category', user_id=anna, name='Dividenden', type='income')
    manual = insert('transaction', user_id=anna, category_id=category, amount=999.0,
                    description='Von Hand gebucht', date=datetime(2026, 8, 20), is_recurring=False, is_paused=False)
    auto_1 = insert('transaction', user_id=anna, category_id=category, amount=1.0,
                    description='Dividende Apple', date=datetime(2026, 8, 15), is_recurring=False, is_paused=False)
    auto_2 = insert('transaction', user_id=anna, category_id=category, amount=1.0,
                    description='Dividende Apple', date=datetime(2026, 8, 15), is_recurring=False, is_paused=False)
    insert('dividend', user_id=anna, asset_id=aapl_1, ex_dividend_date=datetime(2026, 8, 15),
           amount_per_share=0.25, shares_held=4.0, total_amount=1.0, transaction_id=auto_1)
    insert('dividend', user_id=anna, asset_id=aapl_3, ex_dividend_date=datetime(2026, 8, 15),
           amount_per_share=0.25, shares_held=4.0, total_amount=1.0, transaction_id=auto_2)

    return {'anna': anna, 'ben': ben, 'aapl': aapl_1, 'nke': nke, 'manual': manual, 'auto_1': auto_1}


def migrate():
    upgrade()


class TestMigration0003:

    def test_assets_merged_to_oldest(self, old_database):
        migrate()

        assets = rows('SELECT id, symbol FROM asset ORDER BY id')
        assert [(a.id, a.symbol) for a in assets] == [(old_database['aapl'], 'AAPL'), (old_database['nke'], 'NKE')]

    def test_price_history_cleared(self, old_database):
        migrate()

        assert rows('SELECT COUNT(*) AS n FROM price_history')[0].n == 0

    def test_positions_merged_with_weighted_price(self, old_database):
        """2 Stück à 100 + 2 Stück à 200 = 4 Stück à 150, frühestes Kaufdatum bleibt"""
        migrate()

        anna_apple = rows('SELECT quantity, avg_buy_price, bought_at FROM user_asset '
                          'WHERE user_id = :u AND asset_id = :a', u=old_database['anna'], a=old_database['aapl'])
        assert len(anna_apple) == 1
        assert anna_apple[0].quantity == 4.0
        assert anna_apple[0].avg_buy_price == 150.0
        assert str(anna_apple[0].bought_at).startswith('2026-01-01')

    def test_other_users_untouched(self, old_database):
        migrate()

        ben = rows('SELECT asset_id, quantity, avg_buy_price FROM user_asset WHERE user_id = :u', u=old_database['ben'])
        assert [(b.asset_id, b.quantity, b.avg_buy_price) for b in ben] == [(old_database['aapl'], 5.0, 150.0)]
        nike = rows('SELECT quantity FROM user_asset WHERE asset_id = :a', a=old_database['nke'])
        assert [n.quantity for n in nike] == [1.0]

    def test_trades_and_savings_plan_kept_and_relinked(self, old_database):
        """Alle Käufe und der Sparplan bleiben erhalten und hängen am zusammengeführten Asset"""
        migrate()

        trades = rows('SELECT asset_id, quantity FROM asset_transaction WHERE user_id = :u', u=old_database['anna'])
        assert sorted(t.quantity for t in trades) == [2.0, 2.0]
        assert {t.asset_id for t in trades} == {old_database['aapl']}
        plans = rows('SELECT asset_id FROM savings_plan')
        assert [p.asset_id for p in plans] == [old_database['aapl']]

    def test_watchlist_keeps_oldest(self, old_database):
        migrate()

        items = rows('SELECT price_added FROM watchlist WHERE user_id = :u', u=old_database['ben'])
        assert [i.price_added for i in items] == [170.0]

    def test_duplicate_dividend_and_its_booking_removed(self, old_database):
        """Die doppelt gebuchte Dividende samt automatischer Einnahme verschwindet -
        die erste und die von Hand gebuchte Einnahme bleiben"""
        migrate()

        assert rows('SELECT COUNT(*) AS n FROM dividend')[0].n == 1
        remaining = {t.id for t in rows('SELECT id FROM "transaction"')}
        assert remaining == {old_database['manual'], old_database['auto_1']}

    def test_constraints_now_enforced(self, old_database):
        migrate()

        unique = {(c['name'], tuple(c['column_names']))
                  for table in ('asset', 'price_history', 'user_asset', 'watchlist')
                  for c in inspect(db.engine).get_unique_constraints(table)}
        assert ('asset_symbol_key', ('symbol',)) in unique
        assert ('price_history_asset_id_key', ('asset_id', 'date')) in unique
        assert ('user_asset_user_id_key', ('user_id', 'asset_id')) in unique
        assert ('watchlist_user_id_key', ('user_id', 'asset_id')) in unique
        assert 'fx_rate' in inspect(db.engine).get_table_names()
