"""Circuito Santa Bárbara–Huequecura–Ralco, sin inventar ubicaciones."""
from alembic import op
import sqlalchemy as sa

revision = "0003_territory"
down_revision = "0002_search"
branch_labels = depends_on = None


def upgrade():
    op.add_column('comercio', sa.Column('sector', sa.String(50), nullable=False, server_default=''))
    op.add_column('comercio', sa.Column('location_source', sa.Text(), nullable=False, server_default=''))
    op.add_column('comercio', sa.Column('location_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    from backend.models import PuntoInteres, Totem
    PuntoInteres.__table__.create(op.get_bind())
    Totem.__table__.create(op.get_bind())
    op.execute("INSERT INTO totem (id,name,source,verified) VALUES (1,'Tótem Quíbar','',0)")
    op.execute("INSERT INTO comuna (nombre,provincia,region) SELECT 'Alto Biobío','Biobío','Región del Biobío' WHERE NOT EXISTS (SELECT 1 FROM comuna WHERE nombre='Alto Biobío')")


def downgrade():
    raise RuntimeError('Recupera el respaldo previo para revertir sin perder datos territoriales')
