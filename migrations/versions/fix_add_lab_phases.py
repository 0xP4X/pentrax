# revision identifiers, used by Alembic.
revision = 'fix_add_lab_phases'
down_revision = 'f55fe39ae38b_'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'lab_phase',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lab_id', sa.Integer(), sa.ForeignKey('lab.id'), nullable=False),
        sa.Column('order', sa.Integer(), default=1),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table('lab_phase') 