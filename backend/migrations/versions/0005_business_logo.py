"""Permitir logotipo opcional en comercios sin alterar fichas existentes."""
from alembic import op
import sqlalchemy as sa

revision = "0005_business_logo"
down_revision = "0004_demo_interests"
branch_labels = depends_on = None


def upgrade():
    if "logo_archivo" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("comercio")}:
        op.add_column("comercio", sa.Column("logo_archivo", sa.String(255), nullable=False, server_default=""))


def downgrade():
    raise RuntimeError("Recupera el respaldo previo para conservar los logotipos de comercios")
