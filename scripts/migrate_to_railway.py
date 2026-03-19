"""Migrate all tables and data from local PostgreSQL to Railway PostgreSQL.

Usage:
    PYTHONPATH=src uv run python scripts/migrate_to_railway.py

Reads from local DB (DATABASE_URL in .env) and writes to Railway.
Does NOT re-run the pipeline — pure data copy.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from momentum_edge.config import settings
from momentum_edge.db.session import Base
from momentum_edge.db.models import (  # noqa: F401 — register all models with Base
    SectorData,
    Stock,
    EODPrice,
    DeliveryData,
    Fundamentals,
    Indicators,
    Scores,
    Watchlist,
    User,
    Order,
    ScanResult,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOCAL_URL = settings.database_url
RAILWAY_URL = (
    "postgresql://postgres:mTIwfhvdbyUHbTbbQONgkxateboYpVKI"
    "@hopper.proxy.rlwy.net:48674/railway"
)

# Tables to migrate, ordered so FK parents come first
TABLES_ORDERED = [
    "sector_data",
    "stocks",
    "eod_prices",
    "delivery_data",
    "fundamentals",
    "indicators",
    "scores",
    "watchlist",
    "users",
    "orders",
    "scan_results",
]

BATCH_SIZE = 5000

# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------
local_engine = create_engine(LOCAL_URL)
railway_engine = create_engine(RAILWAY_URL, pool_pre_ping=True)

LocalSession = sessionmaker(bind=local_engine)
RailwaySession = sessionmaker(bind=railway_engine)


def create_schema():
    """Create all tables on Railway using SQLAlchemy models."""
    print("Creating schema on Railway...")
    Base.metadata.create_all(railway_engine)
    print("  Schema created.\n")


def get_columns(engine, table_name):
    """Get column names for a table."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t AND table_schema = 'public' "
                "ORDER BY ordinal_position"
            ),
            {"t": table_name},
        )
        return [r[0] for r in result]


def migrate_table(table_name):
    """Copy all rows from local to Railway for a single table."""
    with local_engine.connect() as local_conn:
        count = local_conn.execute(
            text(f'SELECT COUNT(*) FROM "{table_name}"')
        ).scalar()

    if count == 0:
        print(f"  {table_name}: 0 rows — skipping")
        return

    columns = get_columns(local_engine, table_name)
    col_list = ", ".join(f'"{c}"' for c in columns)

    print(f"  {table_name}: {count} rows — migrating...", end="", flush=True)

    # Read all rows from local
    with local_engine.connect() as local_conn:
        rows = local_conn.execute(
            text(f'SELECT {col_list} FROM "{table_name}" ORDER BY "id"')
        ).fetchall()

    # Clear existing data on Railway (in case of re-run)
    with railway_engine.begin() as rw_conn:
        rw_conn.execute(text(f'TRUNCATE "{table_name}" CASCADE'))

    # Insert in batches
    inserted = 0
    placeholders = ", ".join(f":{c}" for c in columns)
    insert_sql = text(
        f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'
    )

    with railway_engine.begin() as rw_conn:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            params = [dict(zip(columns, row)) for row in batch]
            rw_conn.execute(insert_sql, params)
            inserted += len(batch)
            print(f"\r  {table_name}: {inserted}/{count} rows", end="", flush=True)

    # Reset sequence to max id
    with railway_engine.begin() as rw_conn:
        if "id" in columns:
            max_id = rw_conn.execute(
                text(f'SELECT COALESCE(MAX("id"), 0) FROM "{table_name}"')
            ).scalar()
            # Find the sequence name
            seq_result = rw_conn.execute(
                text(
                    f"SELECT pg_get_serial_sequence('{table_name}', 'id')"
                )
            ).scalar()
            if seq_result:
                rw_conn.execute(
                    text(f"SELECT setval('{seq_result}', {max_id})")
                )

    print(f"\r  {table_name}: {count} rows — done ✓")


def verify():
    """Print row counts on Railway for verification."""
    print("\nVerification — Railway row counts:")
    with railway_engine.connect() as conn:
        for t in TABLES_ORDERED:
            try:
                count = conn.execute(
                    text(f'SELECT COUNT(*) FROM "{t}"')
                ).scalar()
                print(f"  {t}: {count}")
            except Exception as e:
                print(f"  {t}: ERROR — {e}")


def main():
    print(f"Source: {LOCAL_URL}")
    print(f"Target: Railway PostgreSQL\n")

    # Test connectivity
    print("Testing Railway connection...")
    with railway_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("  Connected ✓\n")

    create_schema()

    print("Migrating data...")
    for table_name in TABLES_ORDERED:
        migrate_table(table_name)

    verify()
    print("\nMigration complete!")


if __name__ == "__main__":
    main()
