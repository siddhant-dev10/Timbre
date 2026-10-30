"""Database schema migrations for Timbre.

Provides repeatable, idempotent, backward-compatible schema migrations for SQLite
and relational databases. Adds genuinely missing columns and indexes to existing tables
without recreating tables or losing data.
"""
import logging
from typing import Dict, List, Set, Tuple
from sqlalchemy import Engine, inspect, text
from app.database.base import Base
# Import models to ensure Base.metadata is fully populated
import app.models  # noqa: F401

logger = logging.getLogger("timbre.database.migrations")

# Documented additive migrations: (table_name, column_name, column_sql_def)
# In SQLite, ADD COLUMN must be nullable or have a constant DEFAULT value.
ADDITIVE_COLUMNS: List[Tuple[str, str, str]] = [
    ("citizens", "record_source", "VARCHAR(16) NOT NULL DEFAULT 'synthetic'"),
    ("citizens", "archived_at", "DATETIME"),
    ("knowledge_documents", "embedding_model", "VARCHAR(128)"),
    ("knowledge_documents", "embedding_version", "VARCHAR(32)"),
    ("call_jobs", "direction", "VARCHAR(16) NOT NULL DEFAULT 'outbound'"),
]

# Safe index creation statements
SAFE_INDEXES: List[Tuple[str, str, str]] = [
    ("citizens", "ix_citizens_record_source", "CREATE INDEX IF NOT EXISTS ix_citizens_record_source ON citizens (record_source)"),
    ("citizens", "ix_citizens_archived_at", "CREATE INDEX IF NOT EXISTS ix_citizens_archived_at ON citizens (archived_at)"),
    ("knowledge_documents", "ix_knowledge_documents_id", "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_id ON knowledge_documents (id)"),
    ("call_jobs", "ix_call_jobs_direction", "CREATE INDEX IF NOT EXISTS ix_call_jobs_direction ON call_jobs (direction)"),
    ("whatsapp_conversations", "ix_whatsapp_conversations_wa_id", "CREATE INDEX IF NOT EXISTS ix_whatsapp_conversations_wa_id ON whatsapp_conversations (wa_id)"),
    ("whatsapp_messages", "ix_whatsapp_messages_conversation_id", "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_conversation_id ON whatsapp_messages (conversation_id)"),
    ("whatsapp_messages", "ix_whatsapp_messages_wamid", "CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_wamid ON whatsapp_messages (wamid)"),
]


def run_migrations(engine: Engine) -> int:
    """
    Applies repeatable, idempotent, backward-compatible schema migrations.
    Safely adds missing columns and indexes to existing tables without deleting or recreating tables.
    Preserves all existing citizen records, statutory schemes, knowledge documents, and embeddings.
    
    Returns the count of schema modifications applied.
    """
    applied = 0
    # Ensure all declared tables exist
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    # 1. Apply known additive column migrations
    with engine.begin() as conn:
        for table_name, col_name, col_sql in ADDITIVE_COLUMNS:
            if inspector.has_table(table_name):
                existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
                if col_name not in existing_cols:
                    logger.info("Migrating table '%s': adding missing column '%s'", table_name, col_name)
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_sql}"))
                    applied += 1
                else:
                    logger.debug("Table '%s' already has column '%s'; skipping.", table_name, col_name)
            else:
                logger.debug("Table '%s' does not exist yet; will be created by Base.metadata.create_all()", table_name)

    # 2. Dynamic check across all SQLAlchemy models in Base.metadata
    # Re-inspect to see updated columns
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if inspector.has_table(table_name):
                existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
                for column in table.columns:
                    if column.name not in existing_cols:
                        logger.warning(
                            "Found unmigrated column '%s.%s' in model definition; attempting safe additive migration.",
                            table_name, column.name
                        )
                        # Derive safe column type
                        col_type = column.type.compile(dialect=engine.dialect)
                        nullable_str = "" if column.nullable else ""
                        default_clause = ""
                        if column.server_default is not None:
                            default_clause = f" DEFAULT {column.server_default.arg}"
                        elif not column.nullable and column.default is not None:
                            val = column.default.arg
                            default_clause = f" DEFAULT '{val}'" if isinstance(val, str) else f" DEFAULT {val}"

                        sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{default_clause}"
                        conn.execute(text(sql))
                        applied += 1

    # 3. Create safe indexes if supported
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            for table_name, index_name, index_sql in SAFE_INDEXES:
                if inspector.has_table(table_name):
                    try:
                        conn.execute(text(index_sql))
                    except Exception as exc:
                        logger.debug("Index creation notice for '%s': %s", index_name, exc)

    return applied
