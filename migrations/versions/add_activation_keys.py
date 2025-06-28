"""Add activation keys and premium subscriptions

Revision ID: add_activation_keys
Revises: 35c3043fb8f5
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_activation_keys'
down_revision = '35c3043fb8f5'
branch_labels = None
depends_on = None

def upgrade():
    # Create activation_keys table
    op.create_table('activation_key',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('plan_type', sa.String(length=20), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('is_used', sa.Boolean(), default=False),
        sa.Column('used_by', sa.Integer(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['used_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    
    # Create premium_subscription table
    op.create_table('premium_subscription',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('activation_key_id', sa.Integer(), nullable=False),
        sa.Column('plan_type', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.DateTime(), default=datetime.utcnow),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('payment_status', sa.String(length=20), default='completed'),
        sa.Column('amount_paid', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['activation_key_id'], ['activation_key.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('premium_subscription')
    op.drop_table('activation_key') 