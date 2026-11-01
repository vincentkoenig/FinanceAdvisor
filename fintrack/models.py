"""
models.py - Datenbankmodelle für den FinanceAdvisor
Enthält alle SQLAlchemy Modelle für die Datenbank
sowie Pydantic Schemas für das Structured Output des LLMs.
"""

# Standard Library
import secrets

# Third Party
from flask_login import UserMixin
from pydantic import BaseModel as PydanticBaseModel
from typing import List

# Lokale Imports
# db wird in extensions.py angelegt und hier re-exportiert, damit
# bestehende Importe wie "from fintrack.models import db" weiter funktionieren
from fintrack.extensions import db


# ─── SQLALCHEMY MODELLE ───────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    """
    User Tabelle - speichert alle registrierten Nutzer.
    Zentrale Tabelle zu der alle anderen Tabellen eine Verbindung haben.
    is_verified: ob die E-Mail-Adresse per Code bestätigt wurde.
    verification_code: der aktuell gültige 6-stellige Code, wird nach
    erfolgreicher Verifizierung wieder auf None gesetzt.
    verification_code_expires: Ablaufzeitpunkt des Codes, damit alte
    Codes nicht unbegrenzt gültig bleiben.
    verification_attempts: Fehlversuche für den aktuellen Code - nach
    zu vielen Versuchen muss ein neuer Code angefordert werden.
    session_token: steckt in jedem Anmelde-Cookie. Wird er erneuert
    (z.B. beim Ändern des Passworts), sind alle bestehenden Anmeldungen
    auf allen Geräten sofort ungültig.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    password = db.Column(db.String)
    age = db.Column(db.Integer)
    gender = db.Column(db.String)
    risk_profile = db.Column(db.String)
    investment_experience = db.Column(db.String)
    monthly_budget = db.Column(db.Float)
    investment_horizon = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.now())
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String)
    verification_code_expires = db.Column(db.DateTime)
    verification_attempts = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    session_token = db.Column(db.String)

    def get_id(self):
        """
        Kennung für das Anmelde-Cookie: User-ID plus session_token.
        Flask-Login speichert diesen Wert im Cookie und gibt ihn beim
        nächsten Request an load_user() zurück.
        """
        if not self.session_token:
            self.rotate_session_token()
        return f'{self.id}:{self.session_token}'

    def rotate_session_token(self):
        """Erzeugt ein neues session_token und meldet damit alle Geräte ab."""
        self.session_token = secrets.token_urlsafe(32)


class Asset(db.Model):
    """
    Asset Tabelle - speichert alle verfügbaren Finanzprodukte unabhängig vom Nutzer.
    Apple existiert einmal hier, egal wie viele Nutzer Apple besitzen.
    Assets werden automatisch über yfinance erstellt. Jedes Symbol gibt es
    genau einmal.
    currency: Handelswährung des Symbols (z.B. EUR für SAP.DE, USD für AAPL) -
    Kurse werden in dieser Währung gespeichert und erst beim Anzeigen in Euro
    umgerechnet.
    exchange: Börse laut yfinance, z.B. "XETRA" oder "NASDAQ".
    metadata_updated_at: wann Währung, Börse und Typ zuletzt bei yfinance
    abgefragt wurden (NULL = noch nie, wird beim nächsten Kurs-Update geholt).
    """
    __table_args__ = (db.UniqueConstraint('symbol'),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    symbol = db.Column(db.String, nullable=False)
    asset_type = db.Column(db.String)
    currency = db.Column(db.String)
    exchange = db.Column(db.String)
    metadata_updated_at = db.Column(db.DateTime)


class UserAsset(db.Model):
    """
    UserAsset Tabelle - Junction Table zwischen User und Asset.
    Beantwortet: Welcher Nutzer besitzt welches Asset und wie viel?
    Many-to-Many Beziehung: ein Nutzer kann viele Assets haben,
    ein Asset kann vielen Nutzern gehören. Pro Nutzer und Asset gibt es
    genau eine Position - weitere Käufe ändern Menge und Durchschnittspreis.
    """
    __table_args__ = (db.UniqueConstraint('user_id', 'asset_id'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float)
    avg_buy_price = db.Column(db.Float)
    bought_at = db.Column(db.DateTime, default=db.func.now())
    status = db.Column(db.String)


class AssetTransaction(db.Model):
    """
    AssetTransaction Tabelle - protokolliert jeden einzelnen Kauf und
    Verkauf eines Assets als eigene Zeile. Im Unterschied zu UserAsset
    (das nur den aktuellen, aggregierten Zustand hält: Gesamtmenge und
    Durchschnittspreis) bleibt hier die vollständige Historie erhalten,
    auch nachdem sich der Durchschnittspreis durch weitere Käufe ändert.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    type = db.Column(db.String, nullable=False)  # 'buy' oder 'sell'
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)  # Preis pro Einheit zum Zeitpunkt der Transaktion
    date = db.Column(db.DateTime, default=db.func.now())


class SavingsPlan(db.Model):
    """
    SavingsPlan Tabelle - definiert einen wiederkehrenden Sparplan für
    ein bestimmtes Asset. Wird nicht automatisch ausgeführt (Variante B):
    der Nutzer bestätigt jede fällige Ausführung manuell, wodurch eine
    ganz normale AssetTransaction entsteht und last_executed fortgeschrieben wird.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    amount = db.Column(db.Float, nullable=False)  # Betrag pro Ausführung in EUR
    day_of_month = db.Column(db.Integer, nullable=False)  # Tag im Monat, z.B. 1 für den Ersten
    start_date = db.Column(db.DateTime, default=db.func.now())
    last_executed = db.Column(db.DateTime)  # NULL solange noch nie ausgeführt
    active = db.Column(db.Boolean, default=True)


class Dividend(db.Model):
    """
    Dividend Tabelle - protokolliert automatisch erkannte und
    verbuchte Dividendenausschüttungen. Verhindert doppelte
    Verbuchung, indem für jedes (asset_id, ex_dividend_date)-Paar
    nur ein Eintrag existieren kann. Verweist zusätzlich auf die
    erzeugte Transaction im Haushaltsbuch.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    ex_dividend_date = db.Column(db.DateTime, nullable=False)
    amount_per_share = db.Column(db.Float, nullable=False)
    shares_held = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    booked_at = db.Column(db.DateTime, default=db.func.now())


class DailyInsight(db.Model):
    """
    DailyInsight Tabelle - speichert einen täglich automatisch
    generierten, kompakten KI-Text mit den wichtigsten Kennzahlen
    und Entwicklungen des Nutzers (Portfolio + Haushaltsbuch).
    Wird vom Scheduler einmal täglich erzeugt und auf der Home-Seite
    angezeigt, damit die App proaktiv Erkenntnisse liefert statt nur
    auf Anfragen zu reagieren.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())


class PriceHistory(db.Model):
    """
    PriceHistory Tabelle - speichert die Tages-Schlusskurse aller Assets in
    ihrer Handelswährung (Spalte currency). Genau ein Kurs pro Asset und Tag,
    date ist immer Mitternacht des Handelstags.
    Wird vom Scheduler täglich befüllt und für den Wertverlauf genutzt.
    """
    __table_args__ = (db.UniqueConstraint('asset_id', 'date'),)

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    date = db.Column(db.DateTime, default=db.func.now())
    price = db.Column(db.Float)
    currency = db.Column(db.String)


class ChatHistory(db.Model):
    """
    ChatHistory Tabelle - speichert den gesamten Chatverlauf zwischen Nutzer und LLM.
    Wird benötigt damit das LLM den Kontext des Gesprächs versteht.
    role = 'user'      → Nutzer hat geschrieben
    role = 'assistant' → LLM hat geantwortet
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    role = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.now())


class Watchlist(db.Model):
    """
    Watchlist Tabelle - Assets die der Nutzer beobachtet aber noch nicht besitzt.
    Junction Table zwischen User und Asset, jedes Asset höchstens einmal pro Nutzer.
    """
    __table_args__ = (db.UniqueConstraint('user_id', 'asset_id'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    added_at = db.Column(db.DateTime, default=db.func.now())
    price_added = db.Column(db.Float)


class PortfolioAnalysis(db.Model):
    """
    PortfolioAnalysis Tabelle - speichert die KI-generierten Portfolio-Analysen.
    Structured Output vom LLM wird hier als Text gespeichert.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_value = db.Column(db.Float)
    risk_assessment = db.Column(db.Text)
    diversification_score = db.Column(db.Integer)
    summary = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    allocation = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())


class FxRate(db.Model):
    """
    FxRate Tabelle - Wechselkurse pro Tag: rate_to_eur ist der Wert von
    1 Einheit der Währung in Euro (z.B. USD am 2026-10-28: 0.8970).
    Damit werden historische Kurse mit dem Wechselkurs ihres eigenen Tages
    umgerechnet statt mit dem von heute. Ein Eintrag pro Währung und Tag.
    """
    __table_args__ = (db.UniqueConstraint('currency', 'date'),)

    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(3), nullable=False)
    date = db.Column(db.Date, nullable=False)
    rate_to_eur = db.Column(db.Float, nullable=False)


# ─── HAUSHALTSBUCH MODELLE ────────────────────────────────────────────────────

class Category(db.Model):
    """
    Category Tabelle - vom Nutzer verwaltbare Kategorien für das Haushaltsbuch.
    Zweistufig über parent_id: Hauptkategorie (parent_id = NULL) und
    Unterkategorie (parent_id verweist auf die Hauptkategorie).
    type unterscheidet zwischen Einkommen, Fixkosten und variablen Ausgaben.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String, nullable=False)
    type = db.Column(db.String, nullable=False)  # income, fixed_expense oder variable_expense
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))


class Transaction(db.Model):
    """
    Transaction Tabelle - einzelne Einnahmen und Ausgaben des Nutzers.
    Der Typ (Einkommen/Fixkosten/variable Ausgabe) ergibt sich über die
    verknüpfte Category, wird hier nicht separat gespeichert.
    Wiederkehrende Buchungen (is_recurring = True) werden nur einmal
    gespeichert - date ist dann das Startdatum, end_date optional das Ende.
    Sie werden für jeden Monat dazwischen automatisch mitgezählt,
    ohne dass für jeden Monat ein eigener Eintrag existiert.
    is_paused erlaubt es, eine wiederkehrende Buchung vorübergehend
    auszusetzen, ohne sie zu löschen oder ein festes end_date zu setzen.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String)
    date = db.Column(db.DateTime, default=db.func.now())
    is_recurring = db.Column(db.Boolean, default=False)
    end_date = db.Column(db.DateTime)
    is_paused = db.Column(db.Boolean, default=False)
    paused_at = db.Column(db.DateTime)
    # Fingerabdruck eines importierten Kontoumsatzes (imports/bank_service.py), damit
    # derselbe Umsatz bei einem zweiten Import nicht doppelt gebucht wird
    import_hash = db.Column(db.String(40))

    __table_args__ = (db.UniqueConstraint('user_id', 'import_hash'),)


# ─── VERTRÄGE ─────────────────────────────────────────────────────────────────

class Contract(db.Model):
    """
    Contract Tabelle - laufende Verträge des Nutzers (Versicherungen, Strom,
    Handy, Abos, ...), damit Kosten und Kündigungsfristen im Blick bleiben.
    Laufzeit: Die erste Laufzeit dauert min_term_months ab start_date (leer =
    gleich lang wie eine Verlängerung), danach verlängert sich der Vertrag
    jeweils um renewal_months (leer = endet nach der ersten Laufzeit von selbst).
    Kündigen muss man notice_value Tage/Wochen/Monate vor dem Laufzeitende.
    Die Fristen selbst werden nicht gespeichert, sondern in contracts/terms.py
    immer neu berechnet.
    cancelled_at/end_date: wann gekündigt wurde und wann der Vertrag dadurch endet.
    transaction_id: die wiederkehrende Fixkosten-Buchung im Haushaltsbuch, die zu
    diesem Vertrag gehört. Endet der Vertrag, bekommt sie dasselbe Enddatum.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String, nullable=False)
    provider = db.Column(db.String)
    category = db.Column(db.String, nullable=False)  # insurance, energy, telecom, subscription, ...
    contract_number = db.Column(db.String)
    amount = db.Column(db.Float, nullable=False)
    interval = db.Column(db.String, nullable=False)  # monthly, quarterly, half_yearly, yearly
    start_date = db.Column(db.Date, nullable=False)
    min_term_months = db.Column(db.Integer)
    renewal_months = db.Column(db.Integer)
    notice_value = db.Column(db.Integer, nullable=False)
    notice_unit = db.Column(db.String, nullable=False)  # days, weeks, months
    cancelled_at = db.Column(db.Date)
    end_date = db.Column(db.Date)
    notes = db.Column(db.String)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=db.func.now())


# ─── PYDANTIC SCHEMAS ─────────────────────────────────────────────────────────

class AllocationItem(PydanticBaseModel):
    """
    Pydantic Model für ein einzelnes Asset in der Portfolio-Allocation.
    Definiert die Struktur eines einzelnen Eintrags in der Allocation Liste.
    """
    asset: str        # Name des Assets z.B. "Apple"
    value: float      # Wert in EUR z.B. 1500.0
    percentage: float # Prozentualer Anteil am Gesamtportfolio z.B. 100.0


class PortfolioAnalysisSchema(PydanticBaseModel):
    """
    Pydantic Schema für die komplette Portfolio-Analyse.
    Definiert das exakte Format, das das LLM zurückgeben muss.
    Wird als response_format an OpenAI übergeben.
    diversification_score ist bewusst NICHT Teil dieses Schemas -
    er wird serverseitig über den Herfindahl-Hirschman-Index objektiv
    berechnet, statt vom LLM geschätzt zu werden (siehe app.py).
    """
    total_value: float
    currency: str
    allocation: List[AllocationItem]
    risk_assessment: str
    summary: str
    recommendations: list[str]
    disclaimer: str