from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy Objekt erstellen - wird später mit der Flask App verbunden
db = SQLAlchemy()

class User(db.Model):
    """
    User Tabelle - speichert alle registrierten Nutzer
    Zentrale Tabelle zu der alle anderen Tabellen eine Verbindung haben
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


class Asset(db.Model):
    """
    Asset Tabelle - speichert alle verfügbaren Finanzprodukte unabhängig vom Nutzer - Apple existiert einmal hier,
    egal wie viele Nutzer Apple besitzen
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    symbol = db.Column(db.String, nullable=False)
    asset_type = db.Column(db.String)
    currency = db.Column(db.String)


class UserAsset(db.Model):
    """
    UserAsset Tabelle - Junction Table zwischen User und Asset
    Beantwortet: Welcher Nutzer besitzt welches Asset und wie viel?
    Many-to-Many Beziehung: ein Nutzer kann viele Assets haben, ein Asset kann vielen Nutzern gehören
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float)
    avg_buy_price = db.Column(db.Float)
    bought_at = db.Column(db.DateTime, default=db.func.now())
    status = db.Column(db.String)


class PriceHistory(db.Model):
    """
    PriceHistory Tabelle - speichert täglich die Preise aller Assets
    So kann man die Preisentwicklung über Zeit verfolgen
    Ermöglicht dem LLM historische Analysen zu machen
    """
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    date = db.Column(db.DateTime, default=db.func.now())
    price = db.Column(db.Float)
    currency = db.Column(db.String)


class ChatHistory(db.Model):
    """
    ChatHistory Tabelle - speichert den gesamten Chatverlauf
    Wird benötigt damit das LLM den Kontext des Gesprächs versteht
    role = 'user' bedeutet der Nutzer hat geschrieben
    role = 'assistant' bedeutet das LLM hat geantwortet
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    role = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.now())


class Watchlist(db.Model):
    """
    Watchlist Tabelle - Assets die der Nutzer beobachtet aber noch nicht besitzt
    Junction Table zwischen User und Asset
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    added_at = db.Column(db.DateTime, default=db.func.now())

