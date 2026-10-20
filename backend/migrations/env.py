from alembic import context
from backend.models import Base

config = context.config
connection = config.attributes.get("connection")
if connection is None:
    from backend.db import engine
    with engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
else:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
