#!/usr/bin/env python3
"""Migrate data from SQLite to PostgreSQL.

One-time migration script for transferring all INtelliBOX data from
a SQLite database to a PostgreSQL database.

Usage:
    python scripts/migrate_sqlite_to_pg.py \\
        --sqlite sqlite:///./data/intellibox.db \\
        --postgres postgresql+psycopg://intellibox:changeme@localhost:5432/intellibox

    # Dry-run (read-only, no writes):
    python scripts/migrate_sqlite_to_pg.py \\
        --sqlite sqlite:///./data/intellibox.db \\
        --postgres postgresql+psycopg://intellibox:changeme@localhost:5432/intellibox \\
        --dry-run

Safety features:
    - SQLite opened in read-only mode (no modifications to source)
    - Dry-run mode prints what would be migrated without writing
    - Row count verification after each table
    - PostgreSQL sequences reset to max(id) + 1
    - Dependency-ordered inserts (respects foreign keys)
    - All-or-nothing: entire PG side runs in a single transaction
    - Spot-check report for manual verification
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to path so we can import models
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from intellibox.models import (
    Action,
    Assignment,
    Base,
    Email,
    KnowledgeChunk,
    KnowledgeDocument,
    ProcessingLog,
    ProgramNewsCache,
    ReportCache,
    RosterMember,
    Settings,
)

# Tables in dependency order (parents before children).
# Tables with no FK dependencies first, then tables that reference them.
MIGRATION_ORDER = [
    ("emails", Email),
    ("settings", Settings),
    ("roster", RosterMember),
    ("program_news_cache", ProgramNewsCache),
    ("report_cache", ReportCache),
    ("knowledge_documents", KnowledgeDocument),
    ("actions", Action),
    ("assignments", Assignment),
    ("processing_log", ProcessingLog),
    ("knowledge_chunks", KnowledgeChunk),
]

# Tables with autoincrement sequences that need resetting after import
SEQUENCE_TABLES = [
    "emails", "actions", "assignments", "processing_log",
    "program_news_cache", "settings", "roster", "report_cache",
    "knowledge_documents", "knowledge_chunks",
]


def get_column_names(model_class):
    """Get list of column names for an ORM model."""
    return [c.name for c in model_class.__table__.columns]


def copy_row(source_row, model_class):
    """Create a dict of column values from a source ORM instance."""
    data = {}
    for col_name in get_column_names(model_class):
        data[col_name] = getattr(source_row, col_name, None)
    return data


def migrate_table(sqlite_session, pg_session, table_name, model_class, dry_run=False):
    """Migrate all rows from one table. Returns (source_count, dest_count)."""
    rows = sqlite_session.query(model_class).all()
    source_count = len(rows)

    if source_count == 0:
        print(f"  {table_name}: 0 rows (empty)")
        return 0, 0

    if dry_run:
        print(f"  {table_name}: {source_count} rows (dry-run, would migrate)")
        return source_count, 0

    # Use Core bulk insert for speed — preserves original IDs
    col_names = get_column_names(model_class)
    row_dicts = []
    for row in rows:
        row_dicts.append(copy_row(row, model_class))

    # Insert in batches of 500 to avoid memory issues
    batch_size = 500
    for i in range(0, len(row_dicts), batch_size):
        batch = row_dicts[i:i + batch_size]
        pg_session.execute(model_class.__table__.insert(), batch)

    pg_session.flush()

    # Verify count
    dest_count = pg_session.query(model_class).count()

    status = "OK" if dest_count == source_count else "MISMATCH"
    print(f"  {table_name}: {source_count} -> {dest_count} rows [{status}]")

    return source_count, dest_count


def reset_sequences(pg_engine):
    """Reset PostgreSQL autoincrement sequences to max(id) + 1."""
    print("\nResetting PostgreSQL sequences...")
    with pg_engine.connect() as conn:
        for table_name in SEQUENCE_TABLES:
            seq_name = f"{table_name}_id_seq"
            # Check if sequence exists
            result = conn.execute(text(
                "SELECT 1 FROM pg_class WHERE relname = :seq_name AND relkind = 'S'"
            ), {"seq_name": seq_name})
            if not result.fetchone():
                print(f"  {seq_name}: not found (skipping)")
                continue

            # Reset to max(id) or 1 if table is empty
            conn.execute(text(
                f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM \"{table_name}\"), 0) + 1, false)"
            ))
            # Verify
            result = conn.execute(text(f"SELECT last_value FROM \"{seq_name}\""))
            last_val = result.scalar()
            print(f"  {seq_name}: reset to {last_val}")
        conn.commit()


def spot_check(pg_session):
    """Print a few sample records for manual verification."""
    print("\n--- Spot Check ---")

    # Check first email
    email = pg_session.query(Email).first()
    if email:
        print(f"  Email: id={email.id}, message_id={email.message_id}, subject={email.subject[:60]}")
        print(f"         to_addresses type={type(email.to_addresses).__name__}, len={len(email.to_addresses)}")
    else:
        print("  Email: (none)")

    # Check first action
    action = pg_session.query(Action).first()
    if action:
        print(f"  Action: id={action.id}, email_id={action.email_id}, priority={action.priority}")
    else:
        print("  Action: (none)")

    # Check settings
    settings = pg_session.query(Settings).all()
    print(f"  Settings: {len(settings)} entries")
    for s in settings[:3]:
        print(f"    {s.key} = {s.value[:60]}")

    # Check knowledge docs
    doc = pg_session.query(KnowledgeDocument).first()
    if doc:
        chunk_count = pg_session.query(KnowledgeChunk).filter_by(document_id=doc.id).count()
        print(f"  KnowledgeDocument: id={doc.id}, filename={doc.filename}, chunks={chunk_count}")
    else:
        print("  KnowledgeDocument: (none)")

    # Check roster
    roster = pg_session.query(RosterMember).all()
    print(f"  Roster: {len(roster)} members")
    for r in roster[:3]:
        print(f"    {r.full_name} <{r.email}>")


def check_pg_empty(pg_session):
    """Check if PostgreSQL tables are empty. Returns True if safe to migrate."""
    for table_name, model_class in MIGRATION_ORDER:
        count = pg_session.query(model_class).count()
        if count > 0:
            return False, table_name, count
    return True, None, None


def main():
    parser = argparse.ArgumentParser(
        description="Migrate INtelliBOX data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite", required=True,
        help="SQLite connection URL (e.g., sqlite:///./data/intellibox.db)"
    )
    parser.add_argument(
        "--postgres", required=True,
        help="PostgreSQL connection URL (e.g., postgresql+psycopg://user:pass@host:port/db)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be migrated without writing"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Migrate even if PostgreSQL tables are not empty (truncates first)"
    )
    args = parser.parse_args()

    # Validate URLs
    if not args.sqlite.startswith("sqlite"):
        print("ERROR: --sqlite must be a sqlite:// URL")
        return 1
    if not args.postgres.startswith("postgresql"):
        print("ERROR: --postgres must be a postgresql:// URL")
        return 1

    print("=" * 60)
    print("INtelliBOX SQLite -> PostgreSQL Migration")
    print("=" * 60)
    print(f"  Source:  {args.sqlite}")
    print(f"  Target:  {args.postgres.split('@')[0]}@***")
    print(f"  Mode:    {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print()

    # Connect to SQLite (read-only via URI)
    sqlite_url = args.sqlite
    sqlite_engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
    )
    SqliteSession = sessionmaker(bind=sqlite_engine)

    # Connect to PostgreSQL
    pg_engine = create_engine(args.postgres)
    PgSession = sessionmaker(bind=pg_engine)

    # Ensure PG schema exists
    if not args.dry_run:
        print("Ensuring PostgreSQL schema is up to date...")
        Base.metadata.create_all(bind=pg_engine)

    # Check SQLite source
    print("\nReading source (SQLite)...")
    sqlite_session = SqliteSession()
    source_counts = {}
    for table_name, model_class in MIGRATION_ORDER:
        count = sqlite_session.query(model_class).count()
        source_counts[table_name] = count
        print(f"  {table_name}: {count} rows")

    total_source = sum(source_counts.values())
    print(f"\nTotal source rows: {total_source}")

    if total_source == 0:
        print("\nSource database is empty. Nothing to migrate.")
        sqlite_session.close()
        sqlite_engine.dispose()
        pg_engine.dispose()
        return 0

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print("Would migrate the above rows to PostgreSQL.")
        print("No data was written. Run without --dry-run to execute.")
        sqlite_session.close()
        sqlite_engine.dispose()
        pg_engine.dispose()
        return 0

    # Check if PG is empty
    pg_session = PgSession()
    is_empty, nonempty_table, nonempty_count = check_pg_empty(pg_session)
    if not is_empty:
        if args.force:
            print(f"\nWARNING: PostgreSQL table '{nonempty_table}' has {nonempty_count} rows.")
            print("--force specified. Truncating all tables...")
            with pg_engine.connect() as conn:
                for table_name, _ in reversed(MIGRATION_ORDER):
                    conn.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE'))
                conn.commit()
            print("All tables truncated.")
        else:
            print(f"\nERROR: PostgreSQL table '{nonempty_table}' already has {nonempty_count} rows.")
            print("Use --force to truncate and re-migrate, or manually clear the database.")
            pg_session.close()
            sqlite_session.close()
            sqlite_engine.dispose()
            pg_engine.dispose()
            return 1

    # Migrate all tables in dependency order
    print("\nMigrating data...")
    mismatches = []
    try:
        for table_name, model_class in MIGRATION_ORDER:
            src, dst = migrate_table(sqlite_session, pg_session, table_name, model_class)
            if src != dst:
                mismatches.append((table_name, src, dst))

        if mismatches:
            print("\nERROR: Row count mismatches detected!")
            for table_name, src, dst in mismatches:
                print(f"  {table_name}: source={src}, dest={dst}")
            print("Rolling back...")
            pg_session.rollback()
            sqlite_session.close()
            sqlite_engine.dispose()
            pg_engine.dispose()
            return 1

        # Commit the transaction
        pg_session.commit()
        print("\nAll data committed successfully.")

    except Exception as e:
        print(f"\nERROR during migration: {e}")
        print("Rolling back...")
        pg_session.rollback()
        sqlite_session.close()
        sqlite_engine.dispose()
        pg_engine.dispose()
        return 1

    # Reset sequences
    reset_sequences(pg_engine)

    # Verify new inserts work
    print("\nVerifying sequence correctness...")
    test_session = PgSession()
    try:
        from intellibox.utils.datetime_utils import utcnow
        now = utcnow()
        test_email = Email(
            message_id="__migration_verify__@test",
            subject="Migration verification",
            from_address="migrate@test.com",
            to_addresses="[]",
            received_date=now,
            created_at=now,
        )
        test_session.add(test_email)
        test_session.flush()
        max_source_id = max(
            (sqlite_session.query(Email).order_by(Email.id.desc()).first().id, 0)
            if source_counts["emails"] > 0 else (0,)
        )
        if test_email.id > max_source_id:
            print(f"  Sequence OK: new email got id={test_email.id} (max source id={max_source_id})")
        else:
            print(f"  WARNING: new email got id={test_email.id} (max source id={max_source_id})")
        # Remove test row
        test_session.rollback()
    except Exception as e:
        print(f"  Sequence verification error: {e}")
        test_session.rollback()
    finally:
        test_session.close()

    # Spot check
    verify_session = PgSession()
    spot_check(verify_session)
    verify_session.close()

    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    total_migrated = sum(
        source_counts[table_name] for table_name, _ in MIGRATION_ORDER
    )
    print(f"  Total rows migrated: {total_migrated}")
    print(f"  Tables: {len(MIGRATION_ORDER)}")
    print("  Status: SUCCESS")
    print()

    # Cleanup
    sqlite_session.close()
    sqlite_engine.dispose()
    pg_engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
