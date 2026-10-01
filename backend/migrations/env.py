"""Alembic environment. Reads the database URL from the app config, never from alembic.ini."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import config as app_config
from app.db import Base
from app import models  # noqa: F401  (imported so Base.metadata is populated)

cfg = context.config
if cfg.config_file_name:
    fileConfig(cfg.config_file_name)
cfg.set_main_option("sqlalchemy.url", app_config.DATABASE_URL.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=cfg.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      render_as_batch=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(cfg.get_section(cfg.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # render_as_batch lets SQLite alter tables at all: it rebuilds them. PostgreSQL ignores it.
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
