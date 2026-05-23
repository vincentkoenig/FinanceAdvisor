from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String)
    risk_profile = db.Column(db.String)
    investment_experience = db.Column(db.String)
    monthly_budget = db.Column(db.Float)
    investment_horizon = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.now())

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    symbol = db.Column(db.String, nullable=False)
    asset_type = db.Column(db.String)
    currency = db.Column(db.String)

class UserAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Float)
    avg_buy_price = db.Column(db.Float)
    bought_at = db.Column(db.DateTime, default=db.func.now())
    status = db.Column(db.String)

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    date = db.Column(db.DateTime, default=db.func.now())
    price = db.Column(db.Float)
    currency = db.Column(db.String)

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    role = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.now())

class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    added_at = db.Column(db.DateTime, default=db.func.now())

