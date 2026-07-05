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

        # === 新增数据源 ===
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_kline (
                date       DATE NOT NULL,
                code       VARCHAR NOT NULL,
                open       DOUBLE,
                high       DOUBLE,
                low        DOUBLE,
                close      DOUBLE,
                volume     DOUBLE,
                amount     DOUBLE,
                amplitude  DOUBLE,
                turnover   DOUBLE,
                PRIMARY KEY (date, code)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sector_fund_flow (
                date            DATE NOT NULL,
                sector_name     VARCHAR NOT NULL,
                period          VARCHAR NOT NULL DEFAULT '1d',
                net_main        DOUBLE,
                net_super_large DOUBLE,
                net_large       DOUBLE,
                net_medium      DOUBLE,
                net_small       DOUBLE,
                PRIMARY KEY (date, sector_name, period)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_valuation (
                date           DATE NOT NULL,
                index_code     VARCHAR NOT NULL,
                index_name     VARCHAR,
                pe             DOUBLE,
                pb             DOUBLE,
                dividend_yield DOUBLE,
                pe_percentile   DOUBLE,
                pb_percentile   DOUBLE,
                PRIMARY KEY (date, index_code)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bond_yield (
                date        DATE PRIMARY KEY,
                y1          DOUBLE,
                y2          DOUBLE,
                y5          DOUBLE,
                y10         DOUBLE,
                y30         DOUBLE,
                spread_10_2 DOUBLE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS margin_detail (
                date            DATE NOT NULL,
                code            VARCHAR NOT NULL,
                margin_balance  DOUBLE,
                margin_buy      DOUBLE,
                margin_sell     DOUBLE,
                margin_net_buy  DOUBLE,
                short_balance   DOUBLE,
                PRIMARY KEY (date, code)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS huijin_baseline (
                baseline_id         VARCHAR PRIMARY KEY,
                code                VARCHAR NOT NULL,
                name                VARCHAR,
                report_period       VARCHAR,
                report_date         DATE,
                disclosure_date     DATE,
                s0_total_shares     DOUBLE,
                h0_total_shares     DOUBLE,
                a_ratio             DOUBLE,
                source_doc_title    VARCHAR,
                source_doc_url      TEXT,
                source_doc_hash     VARCHAR,
                source_page         VARCHAR,
                verification_status VARCHAR DEFAULT 'draft',
                verified_at         TIMESTAMP,
                is_active           BOOLEAN DEFAULT FALSE,
                CHECK (s0_total_shares IS NULL OR s0_total_shares > 0),
                CHECK (h0_total_shares IS NULL OR h0_total_shares >= 0),
                CHECK (a_ratio IS NULL OR (a_ratio >= 0 AND a_ratio <= 1)),
                CHECK (verification_status IN ('draft', 'verified', 'rejected'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS huijin_baseline_holder (
                baseline_id   VARCHAR NOT NULL,
                holder_name   VARCHAR NOT NULL,
                holder_group  VARCHAR,
                holder_shares DOUBLE,
                holder_ratio  DOUBLE,
                source_line   TEXT,
                CHECK (holder_shares IS NULL OR holder_shares >= 0),
                CHECK (holder_ratio IS NULL OR (holder_ratio >= 0 AND holder_ratio <= 1))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_snapshot_audit (
                date                    DATE NOT NULL,
                code                    VARCHAR NOT NULL,
                source_name             VARCHAR NOT NULL,
                source_url              TEXT,
                source_date             DATE,
                source_date_inferred    BOOLEAN DEFAULT FALSE,
                raw_total_shares        DOUBLE,
                raw_unit                VARCHAR,
                normalized_total_shares DOUBLE,
                run_id                  VARCHAR,
                quality_flags           VARCHAR,
                PRIMARY KEY (date, code, source_name)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_calendar (
                exchange         VARCHAR NOT NULL,
                date             DATE NOT NULL,
                is_trading_day   BOOLEAN DEFAULT FALSE,
                prev_trading_day DATE,
                PRIMARY KEY (exchange, date)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_source_run (
                run_id        VARCHAR PRIMARY KEY,
                task_name     VARCHAR,
                source_name   VARCHAR,
                started_at    TIMESTAMP,
                finished_at   TIMESTAMP,
                status        VARCHAR,
                records_count INTEGER,
                error         TEXT,
                CHECK (status IS NULL OR status IN ('running', 'success', 'failed', 'partial'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_quality_issue (
                issue_id   VARCHAR PRIMARY KEY,
                code       VARCHAR,
                date       DATE,
                issue_type VARCHAR,
                severity   VARCHAR,
                status     VARCHAR DEFAULT 'open',
                message    TEXT,
                created_at TIMESTAMP,
                CHECK (severity IS NULL OR severity IN ('blocker', 'warning', 'info')),
                CHECK (status IS NULL OR status IN ('open', 'resolved', 'ignored'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_share_event (
                event_id          VARCHAR PRIMARY KEY,
                code              VARCHAR NOT NULL,
                event_date        DATE,
                event_type        VARCHAR,
                adjustment_factor DOUBLE,
                source_title      VARCHAR,
                source_url        TEXT,
                is_resolved       BOOLEAN DEFAULT FALSE,
                message           TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS huijin_watch_group (
                group_name VARCHAR NOT NULL,
                code       VARCHAR NOT NULL,
                index_name VARCHAR,
                is_active  BOOLEAN DEFAULT TRUE,
                PRIMARY KEY (group_name, code)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cffex_position_rank (
                date        DATE NOT NULL,
                contract    VARCHAR NOT NULL,
                rank_type   VARCHAR NOT NULL,
                rank_no     INTEGER,
                member_name VARCHAR,
                volume      DOUBLE,
                change      DOUBLE,
                source_name VARCHAR,
                run_id      VARCHAR,
                PRIMARY KEY (date, contract, rank_type, rank_no, member_name)
            )
        """)
    finally:
        conn.close()
