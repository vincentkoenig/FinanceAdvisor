"""baseline schema

Basis-Migration: bildet das Schema ab, das bis zur Einführung von Alembic
über db.create_all() angelegt wurde. Bestehende Datenbanken aus dieser Zeit
werden von "flask upgrade-db" nur als auf diesem Stand markiert (stamp).

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-10-28 21:59:30.875288

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('asset',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('symbol', sa.String(), nullable=False),
    sa.Column('asset_type', sa.String(), nullable=True),
    sa.Column('currency', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('asset_pkey'))
    )
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('password', sa.String(), nullable=True),
    sa.Column('age', sa.Integer(), nullable=True),
    sa.Column('gender', sa.String(), nullable=True),
    sa.Column('risk_profile', sa.String(), nullable=True),
    sa.Column('investment_experience', sa.String(), nullable=True),
    sa.Column('monthly_budget', sa.Float(), nullable=True),
    sa.Column('investment_horizon', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('is_verified', sa.Boolean(), nullable=True),
    sa.Column('verification_code', sa.String(), nullable=True),
    sa.Column('verification_code_expires', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('user_pkey'))
    )
    op.create_table('asset_transaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('price', sa.Float(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], name=op.f('asset_transaction_asset_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('asset_transaction_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('asset_transaction_pkey'))
    )
    op.create_table('category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['category.id'], name=op.f('category_parent_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('category_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('category_pkey'))
    )
    op.create_table('chat_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('role', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('chat_history_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('chat_history_pkey'))
    )
    op.create_table('daily_insight',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('daily_insight_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('daily_insight_pkey'))
    )
    op.create_table('portfolio_analysis',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('total_value', sa.Float(), nullable=True),
    sa.Column('risk_assessment', sa.Text(), nullable=True),
    sa.Column('diversification_score', sa.Integer(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('recommendations', sa.Text(), nullable=True),
    sa.Column('allocation', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('portfolio_analysis_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('portfolio_analysis_pkey'))
    )
    op.create_table('price_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('currency', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], name=op.f('price_history_asset_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('price_history_pkey'))
    )
    op.create_table('savings_plan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('day_of_month', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('last_executed', sa.DateTime(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], name=op.f('savings_plan_asset_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('savings_plan_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('savings_plan_pkey'))
    )
    op.create_table('user_asset',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('quantity', sa.Float(), nullable=True),
    sa.Column('avg_buy_price', sa.Float(), nullable=True),
    sa.Column('bought_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], name=op.f('user_asset_asset_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('user_asset_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('user_asset_pkey'))
    )
    op.create_table('watchlist',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('added_at', sa.DateTime(), nullable=True),
    sa.Column('price_added', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], name=op.f('watchlist_asset_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('watchlist_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('watchlist_pkey'))
    )
    op.create_table('transaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('is_recurring', sa.Boolean(), nullable=True),
    sa.Column('end_date', sa.DateTime(), nullable=True),
    sa.Column('is_paused', sa.Boolean(), nullable=True),
    sa.Column('paused_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], name=op.f('transaction_category_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('transaction_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('transaction_pkey'))
    )
    op.create_table('dividend',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('asset_id', sa.Integer(), nullable=True),
    sa.Column('ex_dividend_date', sa.DateTime(), nullable=False),
    sa.Column('amount_per_share', sa.Float(), nullable=False),
    sa.Column('shares_held', sa.Float(), nullable=False),
    sa.Column('total_amount', sa.Float(), nullable=False),
    sa.Column('transaction_id', sa.Integer(), nullable=True),
    sa.Column('booked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], name=op.f('dividend_asset_id_fkey')),
    sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], name=op.f('dividend_transaction_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('dividend_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('dividend_pkey'))
    )


def downgrade():
    # Entfernt ALLE Tabellen samt Daten - nur für eine leere Testdatenbank gedacht
    op.drop_table('dividend')
    op.drop_table('transaction')
    op.drop_table('watchlist')
    op.drop_table('user_asset')
    op.drop_table('savings_plan')
    op.drop_table('price_history')
    op.drop_table('portfolio_analysis')
    op.drop_table('daily_insight')
    op.drop_table('chat_history')
    op.drop_table('category')
    op.drop_table('asset_transaction')
    op.drop_table('user')
    op.drop_table('asset')
