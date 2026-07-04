import json
import os
from datetime import datetime

from .core import get_conn, query, query_one, execute, execute_many, _to_records, DB_PATH, BASE_DIR, DATA_DIR
from .schema import init_db
import duckdb
import pandas as pd


def _norm_date(s):
    s = str(s).strip().replace('-', '')
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def get_all_etf():
    sql = """
        WITH filled AS (
            SELECT *,
                LAST_VALUE(total_shares IGNORE NULLS) OVER (
                    PARTITION BY code ORDER BY date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS filled_shares
            FROM daily_snapshot
        ),
        with_chg AS (
            SELECT *,
                ROUND((filled_shares - LAG(filled_shares, 1) OVER w) / 1e4, 2) AS chg_1d,
                ROUND((filled_shares - LAG(filled_shares, 5) OVER w) / 1e4, 2) AS chg_5d,
                ROUND((filled_shares - LAG(filled_shares, 21) OVER w) / 1e4, 2) AS chg_21d,
                LAG(filled_shares, 1) OVER w AS prev_shares_1,
                LAG(filled_shares, 5) OVER w AS prev_shares_5,
                LAG(filled_shares, 21) OVER w AS prev_shares_21,
                LAG(price, 1) OVER w AS prev_price_1,
                LAG(price, 5) OVER w AS prev_price_5,
                LAG(price, 21) OVER w AS prev_price_21,
                ROW_NUMBER() OVER (PARTITION BY code ORDER BY CASE WHEN price IS NOT NULL THEN 0 ELSE 1 END, date DESC) AS rn
            FROM filled
            WINDOW w AS (PARTITION BY code ORDER BY date)
        ),
        opt AS (
            SELECT code, call_iv, put_iv, pcr_volume, pcr_oi
            FROM etf_option
            WHERE date = (SELECT MAX(date) FROM etf_option)
        )
        SELECT
            strftime(r.date, '%Y%m%d')                                    AS "日期",
            r.code                                                       AS "代码",
            f.name                                                       AS "名称",
            f.exchange                                                   AS "交易所",
            ROUND(r.filled_shares / 1e8, 4)                              AS "总份额_亿",
            r.chg_1d                                                     AS "份额日改变",
            ROUND(r.chg_1d * 1e4 / NULLIF(r.prev_shares_1, 0) * 100, 2)  AS "份额日改变比例",
            r.chg_5d                                                     AS "份额周改变",
            ROUND(r.chg_5d * 1e4 / NULLIF(r.prev_shares_5, 0) * 100, 2)  AS "份额周改变比例",
            r.chg_21d                                                    AS "份额月改变",
            ROUND(r.chg_21d * 1e4 / NULLIF(r.prev_shares_21, 0) * 100, 2) AS "份额月改变比例",
            r.price                                                      AS "最新价",
            r.price_change_pct                                           AS "涨跌幅",
            ROUND((r.price - r.prev_price_5) / NULLIF(r.prev_price_5, 0) * 100, 2)
                AS "周涨跌幅",
            ROUND((r.price - r.prev_price_21) / NULLIF(r.prev_price_21, 0) * 100, 2)
                AS "月涨跌幅",
            f.huijin_亿                                                   AS "汇金持股_亿",
            ROUND(r.chg_1d * 1e4 / 1e8 / NULLIF(f.huijin_亿, 0) * 100, 4)
                AS "比汇金改变比",
            ROUND(r.turnover / 1e4, 2)                                   AS "成交额_万",
            r.iopv                                                       AS "IOPV",
            r.discount_rt                                                AS "基金折价率",
            ROUND(r.filled_shares / 1e8 * r.price, 4)                    AS "规模_亿",
            ROUND(r.filled_shares / 1e8 * r.price
                - r.prev_shares_1 / 1e8 * COALESCE(r.prev_price_1, r.price), 4)
                AS "规模日改变_亿",
            r.nav                                                        AS "净值",
            r.nav_date                                                   AS "净值日期",
            ROUND((r.price - r.nav) / NULLIF(r.nav, 0) * 100, 2)        AS "净值溢价率",
            f.issuer_nm                                                  AS "基金公司",
            f.index_name                                                 AS "跟踪指数",
            i.change_pct                                                 AS "指数涨跌幅",
            f.inst_hold_pct                                              AS "机构持仓占比",
            o.call_iv                                                    AS "认购IV",
            o.put_iv                                                     AS "认沽IV",
            o.pcr_volume                                                 AS "PCR成交量比",
            v.pe                                                         AS "市盈率PE",
            v.pb                                                         AS "市净率PB",
            v.pe_percentile                                              AS "PE历史分位",
            v.pb_percentile                                              AS "PB历史分位",
            ROUND(m.margin_balance / 1e8, 2)                             AS "融资余额_亿",
            ROUND(m.margin_net_buy / 1e8, 2)                             AS "融资净买入_亿"
        FROM with_chg r
        JOIN fund f ON r.code = f.code
        LEFT JOIN index_spot i ON f.index_code = i.code
        LEFT JOIN opt o ON r.code = o.code
        LEFT JOIN index_valuation v ON f.index_code = v.index_code
            AND v.date = (SELECT MAX(date) FROM index_valuation WHERE index_code = f.index_code)
        LEFT JOIN margin_detail m ON r.code = m.code
            AND m.date = (SELECT MAX(date) FROM margin_detail WHERE code = r.code)
        WHERE r.rn = 1
        ORDER BY
            CASE WHEN f.huijin_亿 IS NOT NULL THEN 0 ELSE 1 END,
            ABS(COALESCE(r.price_change_pct, 0)) DESC
    """
    return _to_records(query(sql))


def get_prices():
    sql = """
        WITH ranked AS (
            SELECT code, date, price, price_change_pct,
                ROW_NUMBER() OVER (PARTITION BY code ORDER BY date DESC) AS rn
            FROM daily_snapshot
            WHERE price IS NOT NULL
        ),
        with_lag AS (
            SELECT code, price, price_change_pct, rn,
                LAG(price, 5)  OVER w AS price_5,
                LAG(price, 21) OVER w AS price_21
            FROM ranked
            WINDOW w AS (PARTITION BY code ORDER BY date)
        )
        SELECT
            r.code,
            r.price              AS "最新价",
            r.price_change_pct   AS "涨跌幅",
            ROUND((r.price - r.price_5)  / NULLIF(r.price_5,  0) * 100, 2) AS "周涨跌幅",
            ROUND((r.price - r.price_21) / NULLIF(r.price_21, 0) * 100, 2) AS "月涨跌幅"
        FROM with_lag r
        WHERE r.rn = 1
    """
    df = query(sql)
    result = {}
    for _, row in df.iterrows():
        code = row['code']
        result[code] = {
            '最新价': None if pd.isna(row['最新价']) else row['最新价'],
            '涨跌幅': None if pd.isna(row['涨跌幅']) else row['涨跌幅'],
            '周涨跌幅': None if pd.isna(row['周涨跌幅']) else row['周涨跌幅'],
            '月涨跌幅': None if pd.isna(row['月涨跌幅']) else row['月涨跌幅'],
        }
    return result


def upsert_snapshots(date_str, records):
    if not records:
        return
    d = _norm_date(date_str)
    sql = """
        INSERT INTO daily_snapshot
            (date, code, total_shares, price, price_change_pct, turnover,
             iopv, discount_rt, nav, nav_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, code) DO UPDATE SET
            total_shares     = COALESCE(EXCLUDED.total_shares,     daily_snapshot.total_shares),
            price            = COALESCE(EXCLUDED.price,            daily_snapshot.price),
            price_change_pct = COALESCE(EXCLUDED.price_change_pct, daily_snapshot.price_change_pct),
            turnover         = COALESCE(EXCLUDED.turnover,         daily_snapshot.turnover),
            iopv             = COALESCE(EXCLUDED.iopv,             daily_snapshot.iopv),
            discount_rt      = COALESCE(EXCLUDED.discount_rt,      daily_snapshot.discount_rt),
            nav              = COALESCE(EXCLUDED.nav,              daily_snapshot.nav),
            nav_date         = COALESCE(EXCLUDED.nav_date,         daily_snapshot.nav_date)
    """
    rows = [(d, c, s, p, pc, t, iopv, disc, nav, nav_d)
            for c, s, p, pc, t, iopv, disc, nav, nav_d in records]
    execute_many(sql, rows)


def batch_update_fund(records):
    if not records:
        return
    sql = """
        INSERT INTO fund (code, name, exchange, huijin_亿, issuer_nm, index_code, index_name)
        VALUES (?, ?, ?, NULL, NULL, NULL, NULL)
        ON CONFLICT (code) DO UPDATE SET
            name     = EXCLUDED.name,
            exchange = EXCLUDED.exchange
    """
    execute_many(sql, records)


def update_fund_info(code, issuer_nm=None, index_code=None, index_name=None):
    sets = []
    params = []
    if issuer_nm is not None:
        sets.append("issuer_nm = ?")
        params.append(issuer_nm)
    if index_code is not None:
        sets.append("index_code = ?")
        params.append(index_code)
    if index_name is not None:
        sets.append("index_name = ?")
        params.append(index_name)
    if not sets:
        return
    params.append(code)
    execute(f"UPDATE fund SET {', '.join(sets)} WHERE code = ?", params)


def upsert_index_spot(records):
    if not records:
        return
    sql = """
        INSERT INTO index_spot (code, name, price, change_pct, update_time)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (code) DO UPDATE SET
            name        = EXCLUDED.name,
            price       = EXCLUDED.price,
            change_pct  = EXCLUDED.change_pct,
            update_time = EXCLUDED.update_time
    """
    execute_many(sql, records)


def get_all_index_spot():
    return _to_records(query("SELECT code, name FROM index_spot"))


def get_funds_without_mapping(limit=50):
    return _to_records(query("""
        SELECT code, name FROM fund WHERE index_code IS NULL
        ORDER BY CASE WHEN huijin_亿 IS NOT NULL THEN 0 ELSE 1 END
        LIMIT ?
    """, [limit]))


def get_funds_without_issuer():
    return _to_records(query("""
        SELECT code, name FROM fund WHERE issuer_nm IS NULL LIMIT 500
    """))


def load_huijin_to_db():
    path = os.path.join(BASE_DIR, 'huijin_config.json')
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    holdings = cfg.get('持仓', {})
    for code, info in holdings.items():
        h = info.get('汇金总持股(亿)')
        if h is not None:
            execute("UPDATE fund SET huijin_亿 = ? WHERE code = ?", [float(h), code])


def get_max_date():
    row = query_one("SELECT MAX(date) AS max_date FROM daily_snapshot")
    return row['max_date'] if row else None


def get_fund_count():
    df = query("SELECT COUNT(*) AS cnt FROM fund")
    return df.iloc[0]['cnt']


def get_snapshot_count():
    df = query("SELECT COUNT(*) AS cnt FROM daily_snapshot")
    return df.iloc[0]['cnt']


def get_index_spot_count():
    df = query("SELECT COUNT(*) AS cnt FROM index_spot")
    return df.iloc[0]['cnt']


def init_task_status(tasks):
    for name, info in tasks.items():
        execute("""
            INSERT INTO task_status (task_name, display_name, schedule_cron, enabled)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (task_name) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                schedule_cron = EXCLUDED.schedule_cron
        """, [name, info['display_name'], info['schedule_cron'], info.get('enabled', True)])


def update_task_status(task_name, status, duration=None, error=None, next_run=None):
    sql = """
        UPDATE task_status
        SET last_run_at = ?,
            last_status = ?,
            last_duration = COALESCE(?, last_duration),
            last_error = ?,
            next_run_at = COALESCE(?, next_run_at)
        WHERE task_name = ?
    """
    now = datetime.now()
    execute(sql, [now, status, duration, error, next_run, task_name])


def get_task_status_all():
    return _to_records(query("""
        SELECT task_name, display_name, schedule_cron, enabled,
               last_run_at, last_status, last_duration, last_error, next_run_at
        FROM task_status ORDER BY task_name
    """))


def toggle_task_enabled(task_name):
    row = query_one("SELECT enabled FROM task_status WHERE task_name = ?", [task_name])
    if row is None:
        raise ValueError(f"Task {task_name} not found")
    new_state = not row['enabled']
    execute("UPDATE task_status SET enabled = ? WHERE task_name = ?", [new_state, task_name])
    return new_state


def write_task_trigger(task_name, action, params=None):
    execute("""
        INSERT INTO task_trigger (id, task_name, action, params, created)
        VALUES (nextval('seq_task_trigger'), ?, ?, ?, ?)
    """, [task_name, action, params, datetime.now()])


def consume_task_triggers(max_retries=5, retry_delay=2):
    import time as _time
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_conn(read_only=False)
            df = conn.execute("""
                UPDATE task_trigger SET consumed = TRUE
                WHERE consumed = FALSE AND created <= NOW()
                RETURNING id, task_name, action, params
            """).fetchdf()
            conn.close()
            return _to_records(df)
        except duckdb.IOException as e:
            if conn is not None:
                conn.close()
            if attempt < max_retries - 1:
                _time.sleep(retry_delay)
                continue
            raise
        except Exception:
            if conn is not None:
                conn.close()
            raise


def get_task_history(task_name, limit=20):
    return _to_records(query("""
        SELECT run_at AS last_run_at, status AS last_status,
               duration AS last_duration, error AS last_error, records_count
        FROM task_history
        WHERE task_name = ?
        ORDER BY run_at DESC LIMIT ?
    """, [task_name, limit]))


def insert_task_history(task_name, status, duration=None, error=None, records_count=None):
    execute("""
        INSERT INTO task_history (id, task_name, run_at, status, duration, error, records_count)
        VALUES (nextval('seq_task_history'), ?, ?, ?, ?, ?, ?)
    """, [task_name, datetime.now(), status, duration, error, records_count])


def get_stats():
    sql = """
        WITH filled AS (
            SELECT *,
                LAST_VALUE(total_shares IGNORE NULLS) OVER (
                    PARTITION BY code ORDER BY date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS filled_shares
            FROM daily_snapshot
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY code ORDER BY date DESC) AS rn
            FROM filled
        )
        SELECT
            COUNT(*) AS total_etf,
            SUM(CASE WHEN price_change_pct > 0 THEN 1 ELSE 0 END) AS up_count,
            SUM(CASE WHEN price_change_pct < 0 THEN 1 ELSE 0 END) AS down_count,
            ROUND(SUM(filled_shares / 1e8 * price), 2) AS total_scale_亿,
            ROUND(AVG(price_change_pct), 2) AS avg_change
        FROM ranked WHERE rn = 1 AND price IS NOT NULL
    """
    return query_one(sql)


def migrate_from_json():
    init_db()

    def _exchange(code):
        c = str(code)
        return '沪' if c.startswith('5') else '深'

    seen_funds = set()
    fund_records = []

    hist_path = os.path.join(DATA_DIR, 'share_history.json')
    if os.path.exists(hist_path):
        with open(hist_path, 'r', encoding='utf-8') as f:
            hist = json.load(f)
        for date_str, codes in hist.items():
            rows = [(c, float(v), None, None, None, None, None, None, None)
                    for c, v in codes.items() if v is not None]
            upsert_snapshots(date_str, rows)
            for c in codes:
                if c not in seen_funds:
                    seen_funds.add(c)
                    fund_records.append((c, '', _exchange(c)))
        batch_update_fund(fund_records)
        print(f"[migrate] imported {len(hist)} days from share_history.json")

    snap_path = os.path.join(DATA_DIR, 'share_snapshots.json')
    if os.path.exists(snap_path):
        with open(snap_path, 'r', encoding='utf-8') as f:
            snaps = json.load(f)
        for date_str, codes in snaps.items():
            rows = [(c, float(v), None, None, None, None, None, None, None)
                    for c, v in codes.items() if v is not None]
            upsert_snapshots(date_str, rows)
            for c in codes:
                if c not in seen_funds:
                    seen_funds.add(c)
                    fund_records.append((c, '', _exchange(c)))
        batch_update_fund(fund_records)
        print(f"[migrate] imported {len(snaps)} days from share_snapshots.json")

    price_path = os.path.join(DATA_DIR, 'price_snapshots.json')
    if os.path.exists(price_path):
        with open(price_path, 'r', encoding='utf-8') as f:
            prices = json.load(f)
        for date_str, codes in prices.items():
            d = _norm_date(date_str)
            for c, p in codes.items():
                if p is not None:
                    execute("""
                        UPDATE daily_snapshot SET price = ?
                        WHERE date = ? AND code = ? AND price IS NULL
                    """, [float(p), d, c])
        print(f"[migrate] merged {len(prices)} days of price data")

    load_huijin_to_db()
    print(f"[migrate] done — {get_fund_count()} funds, {get_snapshot_count()} snapshots")


# ====== 新数据源操作 ======

def upsert_fund_holdings(code, report_date, holdings):
    if not holdings:
        return
    sql = """
        INSERT INTO fund_holding (code, report_date, stock_code, stock_name, hold_pct, hold_amount, hold_value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (code, report_date, stock_code) DO UPDATE SET
            stock_name  = EXCLUDED.stock_name,
            hold_pct    = EXCLUDED.hold_pct,
            hold_amount = EXCLUDED.hold_amount,
            hold_value  = EXCLUDED.hold_value
    """
    rows = [(code, report_date, h['stock_code'], h.get('stock_name'),
             h.get('hold_pct'), h.get('hold_amount'), h.get('hold_value'))
            for h in holdings]
    execute_many(sql, rows)


def get_fund_top_holdings(code, limit=10):
    return _to_records(query("""
        SELECT stock_code, stock_name, hold_pct, hold_amount, hold_value, report_date
        FROM fund_holding
        WHERE code = ?
        ORDER BY report_date DESC, hold_pct DESC
        LIMIT ?
    """, [code, limit]))


def upsert_northbound_flow(records):
    if not records:
        return
    sql = """
        INSERT INTO northbound_flow (date, sh_net, sz_net, total_net, sh_buy, sh_sell, sz_buy, sz_sell)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date) DO UPDATE SET
            sh_net    = EXCLUDED.sh_net,
            sz_net    = EXCLUDED.sz_net,
            total_net = EXCLUDED.total_net,
            sh_buy    = EXCLUDED.sh_buy,
            sh_sell   = EXCLUDED.sh_sell,
            sz_buy    = EXCLUDED.sz_buy,
            sz_sell   = EXCLUDED.sz_sell
    """
    execute_many(sql, records)


def get_northbound_recent(days=30):
    return _to_records(query("""
        SELECT date, sh_net, sz_net, total_net
        FROM northbound_flow
        ORDER BY date DESC LIMIT ?
    """, [days]))


def get_northbound_latest():
    return query_one("""
        SELECT date, sh_net, sz_net, total_net, sh_buy, sh_sell, sz_buy, sz_sell
        FROM northbound_flow ORDER BY date DESC LIMIT 1
    """)


def upsert_etf_option(records):
    if not records:
        return
    sql = """
        INSERT INTO etf_option (code, date, option_code, option_name, call_iv, put_iv, pcr_volume, pcr_oi)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (code, date) DO UPDATE SET
            option_code = EXCLUDED.option_code,
            option_name = EXCLUDED.option_name,
            call_iv     = EXCLUDED.call_iv,
            put_iv      = EXCLUDED.put_iv,
            pcr_volume  = EXCLUDED.pcr_volume,
            pcr_oi      = EXCLUDED.pcr_oi
    """
    execute_many(sql, records)


def get_etf_option_latest():
    return _to_records(query("""
        SELECT code, option_name, call_iv, put_iv, pcr_volume, pcr_oi, date
        FROM etf_option
        WHERE date = (SELECT MAX(date) FROM etf_option)
    """))


def update_fund_inst_hold(code, inst_hold_pct):
    execute("UPDATE fund SET inst_hold_pct = ? WHERE code = ?", [inst_hold_pct, code])


# ─── daily_kline ─────────────────────────────────────────────

def upsert_kline(records):
    if not records:
        return
    sql = """
        INSERT INTO daily_kline (date, code, open, high, low, close, volume, amount, amplitude, turnover)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, code) DO UPDATE SET
            open      = COALESCE(EXCLUDED.open,      daily_kline.open),
            high      = COALESCE(EXCLUDED.high,      daily_kline.high),
            low       = COALESCE(EXCLUDED.low,       daily_kline.low),
            close     = COALESCE(EXCLUDED.close,     daily_kline.close),
            volume    = COALESCE(EXCLUDED.volume,    daily_kline.volume),
            amount    = COALESCE(EXCLUDED.amount,    daily_kline.amount),
            amplitude = COALESCE(EXCLUDED.amplitude, daily_kline.amplitude),
            turnover  = COALESCE(EXCLUDED.turnover,  daily_kline.turnover)
    """
    rows = [(d, c, o, h, l, cl, v, am, amp, t)
            for d, c, o, h, l, cl, v, am, amp, t in records]
    execute_many(sql, rows)


def query_kline(code, limit=120):
    return _to_records(query("""
        SELECT date, open, high, low, close, volume, amount, amplitude, turnover
        FROM daily_kline
        WHERE code = ? AND close IS NOT NULL
        ORDER BY date DESC
        LIMIT ?
    """, [code, limit]))


def get_codes_with_kline():
    df = query("SELECT DISTINCT code FROM daily_kline")
    return set(df['code'].tolist())


# ─── sector_fund_flow ─────────────────────────────────────────

def upsert_sector_fund_flow(records):
    if not records:
        return
    sql = """
        INSERT INTO sector_fund_flow (date, sector_name, net_main, net_super_large, net_large, net_medium, net_small)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, sector_name) DO UPDATE SET
            net_main        = COALESCE(EXCLUDED.net_main,        sector_fund_flow.net_main),
            net_super_large = COALESCE(EXCLUDED.net_super_large, sector_fund_flow.net_super_large),
            net_large       = COALESCE(EXCLUDED.net_large,       sector_fund_flow.net_large),
            net_medium      = COALESCE(EXCLUDED.net_medium,      sector_fund_flow.net_medium),
            net_small       = COALESCE(EXCLUDED.net_small,       sector_fund_flow.net_small)
    """
    rows = [(d, s, nm, nsl, nl, nmd, ns) for d, s, nm, nsl, nl, nmd, ns in records]
    execute_many(sql, rows)


def query_latest_sector_flow():
    return _to_records(query("""
        SELECT sector_name, net_main, net_super_large, net_large, net_medium, net_small
        FROM sector_fund_flow
        WHERE date = (SELECT MAX(date) FROM sector_fund_flow)
        ORDER BY ABS(net_main) DESC
    """))


# ─── index_valuation ───────────────────────────────────────────

def upsert_index_valuation(records):
    if not records:
        return
    sql = """
        INSERT INTO index_valuation (date, index_code, index_name, pe, pb, dividend_yield, pe_percentile, pb_percentile)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, index_code) DO UPDATE SET
            index_name     = COALESCE(EXCLUDED.index_name,     index_valuation.index_name),
            pe             = COALESCE(EXCLUDED.pe,             index_valuation.pe),
            pb             = COALESCE(EXCLUDED.pb,             index_valuation.pb),
            dividend_yield = COALESCE(EXCLUDED.dividend_yield, index_valuation.dividend_yield),
            pe_percentile  = COALESCE(EXCLUDED.pe_percentile,  index_valuation.pe_percentile),
            pb_percentile  = COALESCE(EXCLUDED.pb_percentile,  index_valuation.pb_percentile)
    """
    rows = [(d, ic, inn, pe, pb, dy, pep, pbp) for d, ic, inn, pe, pb, dy, pep, pbp in records]
    execute_many(sql, rows)


def query_latest_index_valuation():
    return _to_records(query("""
        SELECT i.index_code, i.index_name, i.pe, i.pb, i.dividend_yield, i.pe_percentile, i.pb_percentile
        FROM index_valuation i
        INNER JOIN (
            SELECT index_code, MAX(date) AS max_date
            FROM index_valuation GROUP BY index_code
        ) m ON i.index_code = m.index_code AND i.date = m.max_date
    """))


# ─── bond_yield ────────────────────────────────────────────────

def upsert_bond_yield(date_str, y1, y2, y5, y10, y30, spread):
    d = _norm_date(date_str)
    sql = """
        INSERT INTO bond_yield (date, y1, y2, y5, y10, y30, spread_10_2)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date) DO UPDATE SET
            y1          = COALESCE(EXCLUDED.y1,          bond_yield.y1),
            y2          = COALESCE(EXCLUDED.y2,          bond_yield.y2),
            y5          = COALESCE(EXCLUDED.y5,          bond_yield.y5),
            y10         = COALESCE(EXCLUDED.y10,         bond_yield.y10),
            y30         = COALESCE(EXCLUDED.y30,         bond_yield.y30),
            spread_10_2 = COALESCE(EXCLUDED.spread_10_2, bond_yield.spread_10_2)
    """
    execute(sql, [d, y1, y2, y5, y10, y30, spread])


def query_latest_bond_yield():
    return query_one("""
        SELECT date, y1, y2, y5, y10, y30, spread_10_2
        FROM bond_yield
        ORDER BY date DESC LIMIT 1
    """)


# ─── margin_detail ─────────────────────────────────────────────

def upsert_margin_detail(records):
    if not records:
        return
    sql = """
        INSERT INTO margin_detail (date, code, margin_balance, margin_buy, margin_sell, margin_net_buy, short_balance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, code) DO UPDATE SET
            margin_balance = COALESCE(EXCLUDED.margin_balance, margin_detail.margin_balance),
            margin_buy     = COALESCE(EXCLUDED.margin_buy,     margin_detail.margin_buy),
            margin_sell    = COALESCE(EXCLUDED.margin_sell,    margin_detail.margin_sell),
            margin_net_buy = COALESCE(EXCLUDED.margin_net_buy, margin_detail.margin_net_buy),
            short_balance  = COALESCE(EXCLUDED.short_balance,  margin_detail.short_balance)
    """
    rows = [(d, c, mb, mbu, ms, mnb, sb) for d, c, mb, mbu, ms, mnb, sb in records]
    execute_many(sql, rows)


def query_latest_margin():
    return _to_records(query("""
        SELECT code, margin_balance, margin_buy, margin_sell, margin_net_buy, short_balance
        FROM margin_detail
        WHERE date = (SELECT MAX(date) FROM margin_detail)
        ORDER BY ABS(margin_net_buy) DESC
    """))


def get_all_codes():
    df = query("SELECT code FROM fund")
    return [r['code'] for r in _to_records(df)]
