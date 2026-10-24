import os
import sys
from logging.config import fileConfig
from dotenv import load_dotenv

from sqlalchemy import engine_from_config, pool

from alembic import context

# Load .env from backend/
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Add backend/ to sys.path so we can import app.models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base
from app.models import *  # noqa: import all models so metadata is complete

config = context.config

# Override sqlalchemy.url from .env
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pdp_academy.db")
# Alembic must use sync driver for migrations (not aiosqlite)
SYNC_URL = DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
config.set_main_option("sqlalchemy.url", SYNC_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite ALTER support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
