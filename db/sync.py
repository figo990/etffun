import os
import duckdb
import time

from .core import DATA_DIR


def get_db_paths():
    write_path = os.path.join(DATA_DIR, 'etf.duckdb')
    read_path = os.path.join(DATA_DIR, 'etf_read.duckdb')
    return write_path, read_path


def sync_all_tables():
    write_path, read_path = get_db_paths()

    if not os.path.exists(write_path):
        print("[sync] write DB not found, skipping")
        return 0

    tables = None
    return _sync_tables(write_path, read_path, tables)


def sync_tables(table_names):
    write_path, read_path = get_db_paths()
    if not os.path.exists(write_path):
        print("[sync] write DB not found, skipping")
        return 0
    tables = [str(t) for t in (table_names or []) if str(t).strip()]
    if not tables:
        return 0
    return _sync_tables(write_path, read_path, tables)


def _sync_tables(write_path, read_path, table_names=None):
    try:
        read_conn = duckdb.connect(read_path)
        read_conn.execute(f"ATTACH '{write_path}' AS write_db (READ_ONLY)")
    except Exception as e:
        print(f"[sync] ATTACH failed: {e}")
        return 0

    try:
        if table_names is None:
            tables = [r[0] for r in read_conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog='write_db' AND table_schema='main' AND table_type='BASE TABLE'"
            ).fetchall()]
        else:
            tables = table_names

        count = 0
        for table in tables:
            try:
                read_conn.execute(f"""
                    CREATE OR REPLACE TABLE \"{table}\" AS
                    SELECT * FROM write_db.main.\"{table}\"
                """)
                count += 1
            except Exception as e:
                print(f"[sync] table {table}: {e}")

        read_conn.execute("DETACH write_db")
        read_conn.close()
        return count
    except Exception as e:
        print(f"[sync] error: {e}")
        try:
            read_conn.execute("DETACH write_db")
        except Exception:
            pass
        read_conn.close()
        return 0
