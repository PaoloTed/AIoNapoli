"""Database connection and session factory isolated from domain and API layers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def resolve_migrations_dir(migrations_dir: str | Path | None = None) -> Path:
    """Resolve the database/migrations directory relative to repo root."""
    if migrations_dir is not None:
        return Path(migrations_dir)
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "database" / "migrations"
    if candidate.exists():
        return candidate
    return Path("database/migrations")


def resolve_seed_dir(seed_dir: str | Path | None = None) -> Path:
    """Resolve the database/seed directory relative to repo root."""
    if seed_dir is not None:
        return Path(seed_dir)
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "database" / "seed"
    if candidate.exists():
        return candidate
    return Path("database/seed")


def get_sqlite_connection(sqlite_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Create a SQLite connection configured with Row factory and foreign keys."""
    if str(sqlite_path) != ":memory:":
        path = Path(sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
    else:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_postgres_connection(database_url: str) -> Any:
    """Create a PostgreSQL connection via psycopg 3."""
    if not database_url:
        raise ValueError("DATABASE_URL richiesto per il profilo postgres")
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Driver psycopg non installato: installa extra [postgres]") from exc
    return psycopg.connect(database_url, autocommit=False)


def get_connection(
    profile: str,
    *,
    sqlite_path: str = ".data/app.db",
    database_url: str = "",
) -> Any:
    """Create a DB connection according to the active runtime profile."""
    if profile == "sqlite":
        return get_sqlite_connection(sqlite_path)
    if profile == "postgres":
        return get_postgres_connection(database_url)
    raise ValueError(f"Profilo DB non supportato per connessione diretta: {profile}")
