"""
test_models.py - Unit Tests für die SQLAlchemy-Modelle aus models.py.
Prüft grundlegendes Anlegen, Pflichtfelder und Beziehungen zwischen
Tabellen (z.B. Kategorie-Hierarchie über parent_id).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy.exc import IntegrityError

from models import db, User, Category, Transaction, UserAsset, Asset


class TestUserModel:
    """Tests für das User-Model"""

    def test_create_user(self, app):
        """Ein Nutzer kann mit den erwarteten Feldern angelegt werden"""
        user = User(username="max", email="max@test.com", password="hashed_pw")
        db.session.add(user)
        db.session.commit()

        assert user.id is not None
        assert user.username == "max"
        assert user.email == "max@test.com"


class TestCategoryModel:
    """Tests für das Category-Model, insbesondere die Haupt-/Unterkategorie-Hierarchie"""

    def test_subcategory_references_parent(self, app, test_user):
        """Eine Unterkategorie ist über parent_id korrekt mit ihrer
        Hauptkategorie verknüpft"""
        main_category = Category(user_id=test_user.id, name="Wohnen", type="fixed_expense")
        db.session.add(main_category)
        db.session.flush()

        sub_category = Category(
            user_id=test_user.id, name="Miete", type="fixed_expense",
            parent_id=main_category.id
        )
        db.session.add(sub_category)
        db.session.commit()

        assert sub_category.parent_id == main_category.id

    def test_main_category_has_no_parent(self, app, test_user):
        """Eine Hauptkategorie hat keinen parent_id-Wert"""
        category = Category(user_id=test_user.id, name="Einkommen", type="income")
        db.session.add(category)
        db.session.commit()

        assert category.parent_id is None


class TestTransactionModel:
    """Tests für das Transaction-Model, insbesondere die neuen
    Pausierungs-Felder"""

    def test_transaction_default_not_paused(self, app, test_user, income_category):
        """Eine neu angelegte Buchung ist standardmäßig nicht pausiert"""
        from datetime import datetime
        transaction = Transaction(
            user_id=test_user.id,
            category_id=income_category.id,
            amount=100,
            date=datetime.now()
        )
        db.session.add(transaction)
        db.session.commit()

        assert transaction.is_paused is False
        assert transaction.paused_at is None


class TestUserAssetModel:
    """Tests für das UserAsset-Model (Portfolio-Positionen)"""

    def test_create_user_asset(self, app, test_user):
        """Eine Portfolio-Position kann mit Menge und Kaufpreis angelegt werden"""
        asset = Asset(name="Apple Inc.", symbol="AAPL", asset_type="stock", currency="EUR")
        db.session.add(asset)
        db.session.flush()

        user_asset = UserAsset(
            user_id=test_user.id, asset_id=asset.id,
            quantity=5, avg_buy_price=150.0, status="owned"
        )
        db.session.add(user_asset)
        db.session.commit()

        assert user_asset.quantity == 5
        assert user_asset.avg_buy_price == 150.0