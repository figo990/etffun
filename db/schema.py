from .core import DB_PATH
import duckdb


def _ensure_column(conn, table, col, col_type):
    """Add column if it doesn't exist yet (safe migration)."""
    existing = [r[0] for r in conn.execute(
        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'").fetchall()]
    if col not in existing:
        conn.execute(f"ALTER TABLE \"{table}\" ADD COLUMN \"{col}\" {col_type}")
        print(f"  [schema] added column {table}.{col} ({col_type})")


def init_db():
    conn = duckdb.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund (
                code       VARCHAR PRIMARY KEY,
                name       VARCHAR,
                exchange   VARCHAR,
                huijin_亿  DOUBLE,
                issuer_nm  VARCHAR,
                index_code VARCHAR,
                index_name VARCHAR
            )
        """)
        _ensure_column(conn, 'fund', 'issuer_nm',  'VARCHAR')
        _ensure_column(conn, 'fund', 'index_code', 'VARCHAR')
        _ensure_column(conn, 'fund', 'index_name', 'VARCHAR')
        _ensure_column(conn, 'fund', 'inst_hold_pct', 'DOUBLE')

        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_snapshot (
                date             DATE NOT NULL,
                code             VARCHAR NOT NULL,
                total_shares     DOUBLE,
                price            DOUBLE,
                price_change_pct DOUBLE,
                turnover         DOUBLE,
                iopv             DOUBLE,
                discount_rt      DOUBLE,
                nav              DOUBLE,
                nav_date         DATE,
                PRIMARY KEY (date, code)
            )
        """)
        _ensure_column(conn, 'daily_snapshot', 'iopv',        'DOUBLE')
        _ensure_column(conn, 'daily_snapshot', 'discount_rt', 'DOUBLE')
        _ensure_column(conn, 'daily_snapshot', 'nav',         'DOUBLE')
        _ensure_column(conn, 'daily_snapshot', 'nav_date',    'DATE')

        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_spot (
                code        VARCHAR PRIMARY KEY,
                name        VARCHAR,
                price       DOUBLE,
                change_pct  DOUBLE,
                update_time TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_status (
                task_name      VARCHAR PRIMARY KEY,
                display_name   VARCHAR,
                schedule_cron  VARCHAR,
                enabled        BOOLEAN DEFAULT TRUE,
                last_run_at    TIMESTAMP,
                last_status    VARCHAR,
                last_duration  DOUBLE,
                last_error     TEXT,
                next_run_at    TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_trigger (
                id        INTEGER PRIMARY KEY,
                task_name VARCHAR,
                action    VARCHAR,
                params    TEXT,
                created   TIMESTAMP,
                consumed  BOOLEAN DEFAULT FALSE
            )
        """)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_task_trigger START 1
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_holding (
                code          VARCHAR NOT NULL,
                report_date   DATE NOT NULL,
                stock_code    VARCHAR NOT NULL,
                stock_name    VARCHAR,
                hold_pct      DOUBLE,
                hold_amount   DOUBLE,
                hold_value    DOUBLE,
                PRIMARY KEY (code, report_date, stock_code)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS northbound_flow (
                date          DATE PRIMARY KEY,
                sh_net        DOUBLE,
                sz_net        DOUBLE,
                total_net     DOUBLE,
                sh_buy        DOUBLE,
                sh_sell       DOUBLE,
                sz_buy        DOUBLE,
                sz_sell       DOUBLE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS etf_option (
                code          VARCHAR NOT NULL,
                date          DATE NOT NULL,
                option_code   VARCHAR,
                option_name   VARCHAR,
                call_iv       DOUBLE,
                put_iv        DOUBLE,
                pcr_volume    DOUBLE,
                pcr_oi        DOUBLE,
                PRIMARY KEY (code, date)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                id            INTEGER PRIMARY KEY,
                task_name     VARCHAR NOT NULL,
                run_at        TIMESTAMP,
                status        VARCHAR,
                duration      DOUBLE,
                error         TEXT,
                records_count INTEGER
            )
        """)
        conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_task_history START 1
        """)
    finally:
        conn.close()
