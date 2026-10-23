"""Identificar atractivos ficticios sin cambiar los lugares existentes."""
from alembic import op
import sqlalchemy as sa

revision = "0004_demo_interests"
down_revision = "0003_territory"
branch_labels = depends_on = None


def upgrade():
    # 0003 creates the territorial tables from the models on fresh installations.
    if 'demo' not in {column['name'] for column in sa.inspect(op.get_bind()).get_columns('punto_interes')}:
        op.add_column('punto_interes', sa.Column('demo', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    raise RuntimeError('Recupera el respaldo previo para conservar los lugares de demostración')
