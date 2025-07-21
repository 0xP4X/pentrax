from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f56a1b2c'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('learning_path',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('learning_path_lab',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('learning_path_id', sa.Integer(), nullable=False),
        sa.Column('lab_id', sa.Integer(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=True, default=1),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_path.id'], ),
        sa.ForeignKeyConstraint(['lab_id'], ['lab.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('learning_path_completion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('learning_path_id', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('certificate_url', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_path.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('learning_path_completion')
    op.drop_table('learning_path_lab')
    op.drop_table('learning_path') 