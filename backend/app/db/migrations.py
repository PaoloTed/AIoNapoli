"""Idempotent SQL migration runner supporting PostgreSQL and SQLite."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from app.db.session import resolve_migrations_dir


def is_sqlite_connection(conn: Any) -> bool:
    """Return True if connection is a sqlite3.Connection."""
    return isinstance(conn, sqlite3.Connection)


def translate_pg_sql_to_sqlite(sql_text: str) -> str:
    """Convert PostgreSQL DDL in database/migrations/*.sql into SQLite-compatible DDL."""
    lines: list[str] = []
    for raw_line in sql_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("--"):
            continue
        if stripped.upper().startswith("CREATE EXTENSION"):
            continue
        if "USING GIST" in stripped.upper():
            continue
        lines.append(raw_line)
    text = "\n".join(lines)

    # SQLite non supporta ALTER COLUMN ... DROP NOT NULL. Nei test SQLite la
    # colonna è già nullable perché 001_init.sql viene creato ex novo.
    text = re.sub(
        r"ALTER\s+TABLE\s+[\w\"]+\s+ALTER\s+COLUMN\s+[\w\"]+\s+DROP\s+NOT\s+NULL\s*;",
        "",
        text,
        flags=re.IGNORECASE,
    )

    replacements = [
        (r"NOW\(\)\s*-\s*INTERVAL\s*'90 seconds'", "datetime('now', '-90 seconds')"),
        (r"GEOGRAPHY\s*\([^)]+\)", "TEXT"),
        (
            r"BIGINT\s+GENERATED\s+ALWAYS\s+AS\s+IDENTITY\s+PRIMARY\s+KEY",
            "INTEGER PRIMARY KEY AUTOINCREMENT",
        ),
        (r"\bTIMESTAMPTZ\b", "TEXT"),
        (r"\bINTERVAL\b", "TEXT"),
        (r"\bJSONB\b", "TEXT"),
        (r"\bBOOLEAN\b", "INTEGER"),
        (r"\bTRUE\b", "1"),
        (r"\bFALSE\b", "0"),
        (r"NUMERIC\s*\([^)]+\)", "REAL"),
        (r"\bNOW\(\)", "CURRENT_TIMESTAMP"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # SQLite does not support CREATE OR REPLACE VIEW directly
    text = re.sub(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+([a-zA-Z0-9_]+)\s+AS",
        r"DROP VIEW IF EXISTS \1;\nCREATE VIEW \1 AS",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip().rstrip(";")
            if stmt:
                statements.append(stmt)
            current = []
    leftover = "\n".join(current).strip().rstrip(";")
    if leftover:
        statements.append(leftover)
    return statements


def apply_migrations(
    conn: Any,
    migrations_dir: str | Path | None = None,
) -> list[str]:
    """Apply all unapplied SQL migrations in order and return applied filenames."""
    base_dir = resolve_migrations_dir(migrations_dir)
    if not base_dir.exists():
        raise FileNotFoundError(f"Directory migrazioni non trovata: {base_dir}")

    sqlite_mode = is_sqlite_connection(conn)
    cur = conn.cursor()

    if sqlite_mode:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()

    cur.execute("SELECT filename FROM schema_migrations")
    applied_set = {row[0] for row in cur.fetchall()}

    applied_now: list[str] = []
    sql_files = sorted(base_dir.glob("*.sql"))
    for sql_file in sql_files:
        if sql_file.name in applied_set:
            continue
        raw_sql = sql_file.read_text(encoding="utf-8")
        if sqlite_mode and any(
            line.strip() == "-- sqlite: skip" for line in raw_sql.splitlines()[:5]
        ):
            placeholder = "?"
            cur.execute(
                f"INSERT INTO schema_migrations (filename) VALUES ({placeholder})",
                (sql_file.name,),
            )
            conn.commit()
            applied_now.append(sql_file.name)
            continue

        sql_to_run = translate_pg_sql_to_sqlite(raw_sql) if sqlite_mode else raw_sql
        for stmt in _split_sql_statements(sql_to_run):
            cur.execute(stmt)

        placeholder = "?" if sqlite_mode else "%s"
        cur.execute(
            f"INSERT INTO schema_migrations (filename) VALUES ({placeholder})",
            (sql_file.name,),
        )
        conn.commit()
        applied_now.append(sql_file.name)

    return applied_now
