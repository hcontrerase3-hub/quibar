"""Índice FTS5 sincronizado con las fichas del catálogo."""
from alembic import op

revision = "0002_search"
down_revision = "0001_stack"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE VIRTUAL TABLE comercio_fts USING fts5(nombre_fantasia,resumen,descripcion,keywords,ofertas,content='comercio',content_rowid='id',tokenize='unicode61 remove_diacritics 2')")
    op.execute("INSERT INTO comercio_fts(comercio_fts) VALUES ('rebuild')")
    op.execute("""CREATE TRIGGER comercio_fts_insert AFTER INSERT ON comercio BEGIN
      INSERT INTO comercio_fts(rowid,nombre_fantasia,resumen,descripcion,keywords,ofertas)
      VALUES(new.id,new.nombre_fantasia,new.resumen,new.descripcion,new.keywords,new.ofertas); END""")
    op.execute("""CREATE TRIGGER comercio_fts_delete AFTER DELETE ON comercio BEGIN
      INSERT INTO comercio_fts(comercio_fts,rowid,nombre_fantasia,resumen,descripcion,keywords,ofertas)
      VALUES('delete',old.id,old.nombre_fantasia,old.resumen,old.descripcion,old.keywords,old.ofertas); END""")
    op.execute("""CREATE TRIGGER comercio_fts_update AFTER UPDATE ON comercio BEGIN
      INSERT INTO comercio_fts(comercio_fts,rowid,nombre_fantasia,resumen,descripcion,keywords,ofertas)
      VALUES('delete',old.id,old.nombre_fantasia,old.resumen,old.descripcion,old.keywords,old.ofertas);
      INSERT INTO comercio_fts(rowid,nombre_fantasia,resumen,descripcion,keywords,ofertas)
      VALUES(new.id,new.nombre_fantasia,new.resumen,new.descripcion,new.keywords,new.ofertas); END""")


def downgrade():
    for trigger in ("comercio_fts_insert", "comercio_fts_delete", "comercio_fts_update"):
        op.execute(f"DROP TRIGGER {trigger}")
    op.execute("DROP TABLE comercio_fts")
