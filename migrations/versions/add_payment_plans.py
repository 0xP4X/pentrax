"""Add payment plans table

Revision ID: add_payment_plans
Revises: add_activation_keys
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_payment_plans'
down_revision = 'add_activation_keys'
branch_labels = None
depends_on = None

def upgrade():
    # Create payment_plan table
    op.create_table('payment_plan',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert default payment plans
    op.execute("""
        INSERT INTO payment_plan (name, display_name, price, duration_days, description, features) VALUES
        ('monthly', 'Monthly Plan', 9.99, 30, 'Perfect for testing the platform', '["Premium Store Access", "Exclusive Tools", "Priority Support", "30 Days Access"]'),
        ('yearly', 'Yearly Plan', 99.99, 365, 'Best value for long-term users', '["Premium Store Access", "Exclusive Tools", "Priority Support", "365 Days Access", "20% Savings"]'),
        ('lifetime', 'Lifetime Plan', 299.99, 9999, 'One-time payment for permanent access', '["Premium Store Access", "Exclusive Tools", "Priority Support", "Lifetime Access", "All Future Updates"]')
    """)

def downgrade():
    op.drop_table('payment_plan') 