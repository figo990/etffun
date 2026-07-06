import json
import os
import hashlib
import uuid
from datetime import datetime, timedelta

from .core import (
    get_conn, query, query_one, execute, execute_many, _to_records,
    DB_PATH, READ_DB_PATH, BASE_DIR, DATA_DIR,
)
from .schema import init_db
import duckdb
import pandas as pd

_TABLE_EXISTS_CACHE = {}
_TRADING_DAY_CACHE = {}


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


def _nullable_norm_date(value):
    if value is None or value == '':
        return None
    return _norm_date(value)


def _nullable_float(value):
    if value is None or value == '':
        return None
    return float(value)


def _report_period_from_date(value):
    d = _nullable_norm_date(value)
    if not d or len(d) < 7:
        return None
    year = d[:4]
    month = d[5:7]
    if month == '12':
        return f'{year}Y'
    if month == '06':
        return f'{year}H1'
    if month in ('03', '09'):
        return f'{year}Q{int(month) // 3}'
    return year


def _normalize_huijin_baseline(record):
    status = record.get('verification_status') or 'draft'
    if status not in ('draft', 'verified', 'rejected'):
        raise ValueError('verification_status must be draft, verified, or rejected')

    s0 = _nullable_float(record.get('s0_total_shares'))
    h0 = _nullable_float(record.get('h0_total_shares'))
    a_ratio = _nullable_float(record.get('a_ratio'))

    if s0 is not None and s0 <= 0:
        raise ValueError('s0_total_shares must be positive')
    if h0 is not None and h0 < 0:
        raise ValueError('h0_total_shares must be non-negative')
    if a_ratio is not None and not (0 <= a_ratio <= 1):
        raise ValueError('a_ratio must be between 0 and 1')

    if s0 is not None and h0 is not None:
        computed = h0 / s0
        if a_ratio is None:
            a_ratio = computed
        elif abs(a_ratio - computed) > 1e-8:
            raise ValueError('a_ratio must match h0_total_shares / s0_total_shares')

    required = ('baseline_id', 'code')
    missing = [k for k in required if not record.get(k)]
    if missing:
        raise ValueError(f'missing required baseline fields: {", ".join(missing)}')

    if status == 'verified':
        verified_required = (
            'report_period',
            'report_date',
            'disclosure_date',
            's0_total_shares',
            'h0_total_shares',
            'a_ratio',
            'source_doc_title',
            'source_doc_url',
            'source_doc_hash',
            'source_page',
        )
        missing = []
        optional_missing = []
        for key in verified_required:
            value = a_ratio if key == 'a_ratio' else record.get(key)
            if key == 's0_total_shares':
                value = s0
            elif key == 'h0_total_shares':
                value = h0
            if value is None or value == '':
                if key in ('source_doc_url', 'source_doc_hash', 'source_page'):
                    optional_missing.append(key)
                else:
                    missing.append(key)
        if missing:
            raise ValueError(f'verified baseline missing fields: {", ".join(missing)}')
        if optional_missing:
            import logging
            logging.getLogger(__name__).warning(
                'verified baseline %s missing optional fields: %s',
                record.get('baseline_id'), ', '.join(optional_missing))

    return {
        'baseline_id': str(record.get('baseline_id')),
        'code': str(record.get('code')),
        'name': record.get('name'),
        'report_period': record.get('report_period'),
        'report_date': _nullable_norm_date(record.get('report_date')),
        'disclosure_date': _nullable_norm_date(record.get('disclosure_date')),
        's0_total_shares': s0,
        'h0_total_shares': h0,
        'a_ratio': a_ratio,
        'source_doc_title': record.get('source_doc_title'),
        'source_doc_url': record.get('source_doc_url'),
        'source_doc_hash': record.get('source_doc_hash'),
        'source_page': record.get('source_page'),
        'verification_status': status,
        'verified_at': record.get('verified_at'),
        'is_active': bool(record.get('is_active', False)),
    }


def upsert_huijin_baseline(record, holders=None):
    baseline = _normalize_huijin_baseline(record)
    sql = """
        INSERT INTO huijin_baseline (
            baseline_id, code, name, report_period, report_date, disclosure_date,
            s0_total_shares, h0_total_shares, a_ratio, source_doc_title,
            source_doc_url, source_doc_hash, source_page, verification_status,
            verified_at, is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (baseline_id) DO UPDATE SET
            code                = EXCLUDED.code,
            name                = EXCLUDED.name,
            report_period       = EXCLUDED.report_period,
            report_date         = EXCLUDED.report_date,
            disclosure_date     = EXCLUDED.disclosure_date,
            s0_total_shares     = EXCLUDED.s0_total_shares,
            h0_total_shares     = EXCLUDED.h0_total_shares,
            a_ratio             = EXCLUDED.a_ratio,
            source_doc_title    = EXCLUDED.source_doc_title,
            source_doc_url      = EXCLUDED.source_doc_url,
            source_doc_hash     = EXCLUDED.source_doc_hash,
            source_page         = EXCLUDED.source_page,
            verification_status = EXCLUDED.verification_status,
            verified_at         = EXCLUDED.verified_at,
            is_active           = EXCLUDED.is_active
    """
    values = [
        baseline['baseline_id'],
        baseline['code'],
        baseline['name'],
        baseline['report_period'],
        baseline['report_date'],
        baseline['disclosure_date'],
        baseline['s0_total_shares'],
        baseline['h0_total_shares'],
        baseline['a_ratio'],
        baseline['source_doc_title'],
        baseline['source_doc_url'],
        baseline['source_doc_hash'],
        baseline['source_page'],
        baseline['verification_status'],
        baseline['verified_at'],
        baseline['is_active'],
    ]
    execute(sql, values)

    if baseline['is_active']:
        execute("""
            UPDATE huijin_baseline
            SET is_active = FALSE
            WHERE code = ? AND baseline_id <> ?
        """, [baseline['code'], baseline['baseline_id']])

    if holders is not None:
        replace_huijin_baseline_holders(baseline['baseline_id'], holders)

    return baseline['baseline_id']


def replace_huijin_baseline_holders(baseline_id, holders):
    execute("DELETE FROM huijin_baseline_holder WHERE baseline_id = ?", [baseline_id])
    if not holders:
        return
    rows = []
    for holder in holders:
        holder_name = holder.get('holder_name')
        if not holder_name:
            raise ValueError('holder_name is required')
        rows.append((
            baseline_id,
            holder_name,
            holder.get('holder_group'),
            _nullable_float(holder.get('holder_shares')),
            _nullable_float(holder.get('holder_ratio')),
            holder.get('source_line'),
        ))
    execute_many("""
        INSERT INTO huijin_baseline_holder (
            baseline_id, holder_name, holder_group, holder_shares,
            holder_ratio, source_line
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)


def get_huijin_baseline_holders(baseline_id):
    return _to_records(query("""
        SELECT baseline_id, holder_name, holder_group, holder_shares,
               holder_ratio, source_line
        FROM huijin_baseline_holder
        WHERE baseline_id = ?
        ORDER BY holder_group, holder_name
    """, [baseline_id]))


def get_huijin_baseline(baseline_id, include_holders=True):
    row = query_one("""
        SELECT baseline_id, code, name, report_period, report_date,
               disclosure_date, s0_total_shares, h0_total_shares, a_ratio,
               source_doc_title, source_doc_url, source_doc_hash, source_page,
               verification_status, verified_at, is_active
        FROM huijin_baseline
        WHERE baseline_id = ?
    """, [baseline_id])
    if row and include_holders:
        row['holders'] = get_huijin_baseline_holders(baseline_id)
    return row


def get_huijin_baselines(code=None, active_only=False, verified_only=False):
    filters = []
    params = []
    if code is not None:
        filters.append("code = ?")
        params.append(str(code))
    if active_only:
        filters.append("is_active = TRUE")
    if verified_only:
        filters.append("verification_status = 'verified'")
    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    return _to_records(query(f"""
        SELECT baseline_id, code, name, report_period, report_date,
               disclosure_date, s0_total_shares, h0_total_shares, a_ratio,
               source_doc_title, source_doc_url, source_doc_hash, source_page,
               verification_status, verified_at, is_active
        FROM huijin_baseline
        {where_sql}
        ORDER BY code, is_active DESC,
                 CASE verification_status
                     WHEN 'verified' THEN 0
                     WHEN 'draft' THEN 1
                     ELSE 2
                 END,
                 report_date DESC NULLS LAST,
                 disclosure_date DESC NULLS LAST
    """, params))


def get_active_huijin_baseline(code, as_of_date=None, verified_only=True):
    filters = ["code = ?", "is_active = TRUE"]
    params = [str(code)]
    if verified_only:
        filters.append("verification_status = 'verified'")
    if as_of_date is not None:
        filters.append("disclosure_date IS NOT NULL AND disclosure_date <= ?")
        params.append(_nullable_norm_date(as_of_date))
    return query_one(f"""
        SELECT baseline_id, code, name, report_period, report_date,
               disclosure_date, s0_total_shares, h0_total_shares, a_ratio,
               source_doc_title, source_doc_url, source_doc_hash, source_page,
               verification_status, verified_at, is_active
        FROM huijin_baseline
        WHERE {' AND '.join(filters)}
        ORDER BY disclosure_date DESC NULLS LAST, report_date DESC NULLS LAST
        LIMIT 1
    """, params)


def seed_huijin_baselines_from_config():
    path = os.path.join(BASE_DIR, 'huijin_config.json')
    if not os.path.exists(path):
        return 0
    with open(path, 'r', encoding='utf-8') as f:
        cfg = json.load(f) or {}

    update_date = _nullable_norm_date(cfg.get('更新日期'))
    disclosure_date = _nullable_norm_date(cfg.get('披露日期')) or update_date
    report_period = _report_period_from_date(update_date)
    source_title = cfg.get('数据来源') or cfg.get('说明摘要') or 'huijin_config.json'
    holdings = cfg.get('持仓', {}) or {}

    count = 0
    for code, info in holdings.items():
        # Skip if a verified baseline already exists for this code
        existing = query_one("""
            SELECT 1 FROM huijin_baseline
            WHERE code = ? AND verification_status = 'verified' AND is_active = true
            LIMIT 1
        """, [code])
        if existing:
            continue
        # Secondary check on write DB to avoid stale read replica
        from db.core import query as _q
        df = _q("""
            SELECT 1 FROM huijin_baseline
            WHERE code = ? AND verification_status = 'verified' AND is_active = true
            LIMIT 1
        """, [code], read_only=False)
        if df is not None and not df.empty:
            continue
            continue
        info = info or {}
        h_yi = _nullable_float(info.get('汇金总持股(亿)'))
        h0 = h_yi * 1e8 if h_yi is not None else None
        # Determine if this holding has verified data (has both holding value and source doc URL)
        has_h0 = h_yi is not None
        has_doc = bool(info.get('来源公告'))
        is_verified = has_h0 and has_doc
        baseline_id = f"huijin-config-{code}-{(update_date or 'unknown').replace('-', '')}"
        doc_url = info.get('来源公告')
        doc_hash = hashlib.sha256(f"{baseline_id}:{doc_url or ''}".encode()).hexdigest()[:16] if is_verified else None
        upsert_huijin_baseline({
            'baseline_id': baseline_id,
            'code': code,
            'name': info.get('名称'),
            'report_period': report_period,
            'report_date': update_date,
            'disclosure_date': disclosure_date,
            's0_total_shares': None,
            'h0_total_shares': h0,
            'a_ratio': None,
            'source_doc_title': source_title,
            'source_doc_url': doc_url,
            'source_doc_hash': doc_hash,
            'source_page': '基金2025年年报',
            'verification_status': 'verified' if is_verified else 'draft',
            'verified_at': datetime.now() if is_verified else None,
            'is_active': is_verified,
        }, holders=None)
        count += 1
    return count


def bootstrap_huijin_support_data(as_of_date=None, calendar_days_back=760,
                                  calendar_days_forward=370, refresh_issues=False,
                                  sync_read=False):
    """Seed non-authoritative Huijin support data without promoting baselines."""
    if as_of_date is None:
        as_of_date = get_max_date() or datetime.now().strftime('%Y-%m-%d')
    as_of = _nullable_norm_date(as_of_date)
    base = _parse_date(as_of)

    result = {
        'draft_baselines': seed_huijin_baselines_from_config(),
        'watch_groups': seed_huijin_watch_groups(),
        'market_calendar': 0,
        'quality_issues': 0,
        'synced_tables': 0,
    }

    calendar_count = query_one("SELECT COUNT(*) AS cnt FROM market_calendar") or {}
    if int(calendar_count.get('cnt') or 0) == 0:
        start = (base - timedelta(days=calendar_days_back)).strftime('%Y-%m-%d')
        end = (base + timedelta(days=calendar_days_forward)).strftime('%Y-%m-%d')
        result['market_calendar'] = seed_market_calendar(start, end)

    if refresh_issues:
        result['quality_issues'] = refresh_huijin_data_quality_issues()

    if sync_read and os.path.abspath(DB_PATH) != os.path.abspath(READ_DB_PATH):
        from .sync import sync_tables
        tables = [
            'huijin_baseline',
            'huijin_baseline_holder',
            'huijin_watch_group',
            'market_calendar',
            'data_source_run',
        ]
        if refresh_issues:
            tables.append('data_quality_issue')
        result['synced_tables'] = sync_tables(tables)

    return result


def _table_exists(table):
    if table in _TABLE_EXISTS_CACHE:
        return _TABLE_EXISTS_CACHE[table]
    row = query_one("""
        SELECT COUNT(*) AS cnt
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
    """, [table])
    exists = bool(row and row.get('cnt'))
    _TABLE_EXISTS_CACHE[table] = exists
    return exists


def _code_exchange(code):
    c = str(code)
    if c.startswith('5'):
        return 'SSE'
    if c.startswith('1'):
        return 'SZSE'
    return 'CN'


def _display_exchange(exchange):
    if exchange in ('SSE', '沪'):
        return '沪'
    if exchange in ('SZSE', '深'):
        return '深'
    return exchange


def _parse_date(value):
    return datetime.strptime(_nullable_norm_date(value), '%Y-%m-%d')


def _is_weekday(value):
    return _parse_date(value).weekday() < 5


def _previous_weekday(value, include_self=True):
    d = _parse_date(value)
    if not include_self:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def infer_trading_date(base_date=None, exchange='CN'):
    """Infer a trading date from a run date using calendar data or weekday fallback."""
    if base_date is None:
        base_date = datetime.now().strftime('%Y-%m-%d')
    if isinstance(base_date, datetime):
        base_date = base_date.strftime('%Y-%m-%d')
    d = _nullable_norm_date(base_date)
    if _table_exists('market_calendar'):
        row = query_one("""
            SELECT MAX(date) AS date
            FROM market_calendar
            WHERE exchange IN (?, 'CN') AND date <= ? AND is_trading_day = TRUE
        """, [exchange, d])
        if row and row.get('date'):
            return row['date']
    return _previous_weekday(d, include_self=True)


def is_trading_day(date_str, exchange='CN'):
    d = _nullable_norm_date(date_str)
    if d is None:
        return False
    key = (exchange, d)
    if key in _TRADING_DAY_CACHE:
        return _TRADING_DAY_CACHE[key]
    if _table_exists('market_calendar'):
        row = query_one("""
            SELECT is_trading_day
            FROM market_calendar
            WHERE exchange IN (?, 'CN') AND date = ?
            ORDER BY CASE WHEN exchange = ? THEN 0 ELSE 1 END
            LIMIT 1
        """, [exchange, d, exchange])
        if row is not None and row.get('is_trading_day') is not None:
            result = bool(row['is_trading_day'])
            _TRADING_DAY_CACHE[key] = result
            return result
    result = _is_weekday(d)
    _TRADING_DAY_CACHE[key] = result
    return result


def seed_market_calendar(start_date, end_date, exchanges=None):
    if exchanges is None:
        exchanges = ['SSE', 'SZSE', 'CFFEX', 'CN']
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    rows = []
    for exchange in exchanges:
        prev = None
        d = start
        while d <= end:
            is_open = d.weekday() < 5
            date_s = d.strftime('%Y-%m-%d')
            rows.append((exchange, date_s, is_open, prev))
            if is_open:
                prev = date_s
            d += timedelta(days=1)
    execute_many("""
        INSERT INTO market_calendar (exchange, date, is_trading_day, prev_trading_day)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (exchange, date) DO UPDATE SET
            is_trading_day = EXCLUDED.is_trading_day,
            prev_trading_day = EXCLUDED.prev_trading_day
    """, rows)
    _TRADING_DAY_CACHE.clear()
    return len(rows)


def seed_market_calendar_from_trading_dates(trading_dates, start_date=None, end_date=None, exchanges=None):
    if exchanges is None:
        exchanges = ['SSE', 'SZSE', 'CFFEX', 'CN']
    normalized = sorted({
        _nullable_norm_date(d)
        for d in (trading_dates or [])
        if _nullable_norm_date(d)
    })
    if not normalized:
        return 0
    start = _parse_date(start_date or normalized[0])
    end = _parse_date(end_date or normalized[-1])
    trading_set = {
        d for d in normalized
        if start.strftime('%Y-%m-%d') <= d <= end.strftime('%Y-%m-%d')
    }
    rows = []
    for exchange in exchanges:
        prev = None
        d = start
        while d <= end:
            date_s = d.strftime('%Y-%m-%d')
            is_open = date_s in trading_set
            rows.append((exchange, date_s, is_open, prev))
            if is_open:
                prev = date_s
            d += timedelta(days=1)
    return upsert_market_calendar(rows)


def upsert_market_calendar(records):
    rows = []
    for r in records or []:
        if isinstance(r, dict):
            rows.append((
                r.get('exchange') or 'CN',
                _nullable_norm_date(r.get('date')),
                bool(r.get('is_trading_day')),
                _nullable_norm_date(r.get('prev_trading_day')),
            ))
        else:
            exchange, date, is_trading_day, prev_trading_day = r
            rows.append((
                exchange or 'CN',
                _nullable_norm_date(date),
                bool(is_trading_day),
                _nullable_norm_date(prev_trading_day),
            ))
    rows = [r for r in rows if r[1]]
    execute_many("""
        INSERT INTO market_calendar (exchange, date, is_trading_day, prev_trading_day)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (exchange, date) DO UPDATE SET
            is_trading_day = EXCLUDED.is_trading_day,
            prev_trading_day = EXCLUDED.prev_trading_day
    """, rows)
    _TRADING_DAY_CACHE.clear()
    return len(rows)


def create_data_source_run(task_name, source_name, run_id=None, started_at=None):
    run_id = run_id or f"{task_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    started_at = started_at or datetime.now()
    execute("""
        INSERT INTO data_source_run (
            run_id, task_name, source_name, started_at, finished_at,
            status, records_count, error
        )
        VALUES (?, ?, ?, ?, NULL, 'running', 0, NULL)
        ON CONFLICT (run_id) DO UPDATE SET
            task_name = EXCLUDED.task_name,
            source_name = EXCLUDED.source_name,
            started_at = EXCLUDED.started_at,
            status = EXCLUDED.status,
            records_count = EXCLUDED.records_count,
            error = EXCLUDED.error
    """, [run_id, task_name, source_name, started_at])
    return run_id


def finish_data_source_run(run_id, status, records_count=None, error=None, finished_at=None):
    finished_at = finished_at or datetime.now()
    execute("""
        UPDATE data_source_run
        SET finished_at = ?,
            status = ?,
            records_count = COALESCE(?, records_count),
            error = ?
        WHERE run_id = ?
    """, [finished_at, status, records_count, error, run_id])


def upsert_daily_snapshot_audit(records):
    if not records:
        return 0
    rows = []
    for r in records:
        rows.append((
            _nullable_norm_date(r.get('date')),
            str(r.get('code')),
            r.get('source_name'),
            r.get('source_url'),
            _nullable_norm_date(r.get('source_date')),
            bool(r.get('source_date_inferred', False)),
            _nullable_float(r.get('raw_total_shares')),
            r.get('raw_unit'),
            _nullable_float(r.get('normalized_total_shares')),
            r.get('run_id'),
            r.get('quality_flags'),
        ))
    execute_many("""
        INSERT INTO daily_snapshot_audit (
            date, code, source_name, source_url, source_date,
            source_date_inferred, raw_total_shares, raw_unit,
            normalized_total_shares, run_id, quality_flags
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, code, source_name) DO UPDATE SET
            source_url = EXCLUDED.source_url,
            source_date = EXCLUDED.source_date,
            source_date_inferred = EXCLUDED.source_date_inferred,
            raw_total_shares = EXCLUDED.raw_total_shares,
            raw_unit = EXCLUDED.raw_unit,
            normalized_total_shares = EXCLUDED.normalized_total_shares,
            run_id = EXCLUDED.run_id,
            quality_flags = EXCLUDED.quality_flags
    """, rows)
    return len(rows)


def get_daily_snapshot_audit(code=None, date=None, source_name=None, limit=200):
    filters = []
    params = []
    if code is not None:
        filters.append("code = ?")
        params.append(str(code))
    if date is not None:
        filters.append("date = ?")
        params.append(_nullable_norm_date(date))
    if source_name is not None:
        filters.append("source_name = ?")
        params.append(source_name)
    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    params.append(limit)
    return _to_records(query(f"""
        SELECT date, code, source_name, source_url, source_date,
               source_date_inferred, raw_total_shares, raw_unit,
               normalized_total_shares, run_id, quality_flags
        FROM daily_snapshot_audit
        {where_sql}
        ORDER BY date DESC, source_name
        LIMIT ?
    """, params))


def backfill_huijin_daily_snapshot_audit(run_id='legacy-huijin-share-audit'):
    codes = _huijin_codes()
    if not codes:
        return 0
    codes_sql = ','.join(_quote_sql(c) for c in codes)
    before = query_one(f"""
        SELECT COUNT(*) AS cnt
        FROM daily_snapshot s
        WHERE s.code IN ({codes_sql})
          AND s.total_shares IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM daily_snapshot_audit a
              WHERE a.date = s.date
                AND a.code = s.code
                AND a.source_name = 'legacy_daily_snapshot'
          )
    """) or {}
    execute(f"""
        INSERT INTO daily_snapshot_audit (
            date, code, source_name, source_url, source_date, source_date_inferred,
            raw_total_shares, raw_unit, normalized_total_shares, run_id, quality_flags
        )
        SELECT s.date,
               s.code,
               'legacy_daily_snapshot',
               NULL,
               s.date,
               TRUE,
               s.total_shares,
               '份',
               s.total_shares,
               ?,
               'SOURCE_AUDIT_BACKFILLED'
        FROM daily_snapshot s
        WHERE s.code IN ({codes_sql})
          AND s.total_shares IS NOT NULL
        ON CONFLICT (date, code, source_name) DO UPDATE SET
            source_date = EXCLUDED.source_date,
            source_date_inferred = EXCLUDED.source_date_inferred,
            raw_total_shares = EXCLUDED.raw_total_shares,
            raw_unit = EXCLUDED.raw_unit,
            normalized_total_shares = EXCLUDED.normalized_total_shares,
            run_id = EXCLUDED.run_id,
            quality_flags = EXCLUDED.quality_flags
    """, [run_id])
    return int(before.get('cnt') or 0)


def _flag_set(value):
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(v).strip() for v in value if str(v).strip()}
    return {
        p.strip()
        for p in str(value).replace(';', ',').replace('|', ',').split(',')
        if p.strip()
    }


def _quality_issue_id(prefix, issue):
    raw = '|'.join([
        prefix,
        str(issue.get('issue_type') or ''),
        str(issue.get('code') or ''),
        str(issue.get('date') or ''),
        str(issue.get('message') or ''),
    ])
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]}"


def upsert_data_quality_issues(issues, prefix='manual', resolve_missing=False):
    if not issues:
        if resolve_missing:
            execute("""
                UPDATE data_quality_issue
                SET status = 'resolved'
                WHERE issue_id LIKE ? AND status = 'open'
            """, [f'{prefix}-%'])
        return 0
    now = datetime.now()
    rows = []
    issue_ids = []
    for issue in issues:
        issue_id = issue.get('issue_id') or _quality_issue_id(prefix, issue)
        issue_ids.append(issue_id)
        rows.append((
            issue_id,
            issue.get('code'),
            _nullable_norm_date(issue.get('date')),
            issue.get('issue_type'),
            issue.get('severity'),
            issue.get('status') or 'open',
            issue.get('message'),
            issue.get('created_at') or now,
        ))
    execute_many("""
        INSERT INTO data_quality_issue (
            issue_id, code, date, issue_type, severity, status, message, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (issue_id) DO UPDATE SET
            code = EXCLUDED.code,
            date = EXCLUDED.date,
            issue_type = EXCLUDED.issue_type,
            severity = EXCLUDED.severity,
            status = EXCLUDED.status,
            message = EXCLUDED.message
    """, rows)
    if resolve_missing:
        keep = ','.join(_quote_sql(i) for i in issue_ids)
        execute(f"""
            UPDATE data_quality_issue
            SET status = 'resolved'
            WHERE issue_id LIKE {_quote_sql(prefix + '-%')}
              AND status = 'open'
              AND issue_id NOT IN ({keep})
        """)
    return len(rows)


def get_data_quality_issues(code=None, status='open', severity=None, limit=500):
    filters = []
    params = []
    if code is not None:
        filters.append("(code = ? OR code IS NULL)")
        params.append(str(code))
    if status is not None:
        filters.append("status = ?")
        params.append(status)
    if severity is not None:
        filters.append("severity = ?")
        params.append(severity)
    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    params.append(limit)
    return _to_records(query(f"""
        SELECT issue_id, code, date, issue_type, severity, status, message, created_at
        FROM data_quality_issue
        {where_sql}
        ORDER BY CASE severity
                     WHEN 'blocker' THEN 0
                     WHEN 'warning' THEN 1
                     ELSE 2
                 END,
                 created_at DESC
        LIMIT ?
    """, params))


def refresh_huijin_data_quality_issues():
    audit = audit_huijin_data(include_persistent=False)
    issues = audit.get('issues', [])
    return upsert_data_quality_issues(issues, prefix='huijin', resolve_missing=True)


def upsert_fund_share_events(records):
    if not records:
        return 0
    rows = []
    for r in records:
        event_id = r.get('event_id') or _quality_issue_id('share-event', {
            'issue_type': r.get('event_type'),
            'code': r.get('code'),
            'date': r.get('event_date'),
            'message': r.get('source_title') or r.get('message'),
        })
        rows.append((
            event_id,
            str(r.get('code')),
            _nullable_norm_date(r.get('event_date')),
            r.get('event_type'),
            _nullable_float(r.get('adjustment_factor')),
            r.get('source_title'),
            r.get('source_url'),
            bool(r.get('is_resolved', False)),
            r.get('message'),
        ))
    execute_many("""
        INSERT INTO fund_share_event (
            event_id, code, event_date, event_type, adjustment_factor,
            source_title, source_url, is_resolved, message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (event_id) DO UPDATE SET
            code = EXCLUDED.code,
            event_date = EXCLUDED.event_date,
            event_type = EXCLUDED.event_type,
            adjustment_factor = EXCLUDED.adjustment_factor,
            source_title = EXCLUDED.source_title,
            source_url = EXCLUDED.source_url,
            is_resolved = EXCLUDED.is_resolved,
            message = EXCLUDED.message
    """, rows)
    return len(rows)


def get_fund_share_events(code=None, start_date=None, end_date=None, unresolved_only=False):
    filters = []
    params = []
    if code is not None:
        filters.append("code = ?")
        params.append(str(code))
    if start_date is not None:
        filters.append("event_date >= ?")
        params.append(_nullable_norm_date(start_date))
    if end_date is not None:
        filters.append("event_date <= ?")
        params.append(_nullable_norm_date(end_date))
    if unresolved_only:
        filters.append("is_resolved = FALSE")
    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    return _to_records(query(f"""
        SELECT event_id, code, event_date, event_type, adjustment_factor,
               source_title, source_url, is_resolved, message
        FROM fund_share_event
        {where_sql}
        ORDER BY event_date DESC NULLS LAST, code
    """, params))


_DEFAULT_HUIJIN_GROUPS = [
    ('上证50', '510050', '上证50'),
    ('沪深300', '510300', '沪深300'),
    ('沪深300', '159919', '沪深300'),
    ('沪深300', '510330', '沪深300'),
    ('中证500', '510500', '中证500'),
    ('中证500', '512500', '中证500'),
    ('中证500', '159922', '中证500'),
    ('中证1000', '512100', '中证1000'),
    ('中证1000', '159845', '中证1000'),
    ('创业板', '159915', '创业板'),
    ('创业板', '159952', '创业板'),
    ('科创50', '588080', '科创50'),
    ('上证180', '510180', '上证180'),
    ('上证180金融', '510230', '上证180金融'),
    ('科创50', '588000', '科创50'),
]


def seed_huijin_watch_groups():
    rows = [(g, c, i, True) for g, c, i in _DEFAULT_HUIJIN_GROUPS]
    execute_many("""
        INSERT INTO huijin_watch_group (group_name, code, index_name, is_active)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (group_name, code) DO UPDATE SET
            index_name = EXCLUDED.index_name,
            is_active = EXCLUDED.is_active
    """, rows)
    return len(rows)


def get_huijin_watch_groups(active_only=True):
    where_sql = "WHERE is_active = TRUE" if active_only else ""
    rows = _to_records(query(f"""
        SELECT group_name, code, index_name, is_active
        FROM huijin_watch_group
        {where_sql}
        ORDER BY group_name, code
    """))
    if rows:
        return rows
    return [
        {'group_name': g, 'code': c, 'index_name': i, 'is_active': True}
        for g, c, i in _DEFAULT_HUIJIN_GROUPS
    ]


def upsert_cffex_position_rank(records):
    if not records:
        return 0
    rows = []
    for r in records:
        rows.append((
            _nullable_norm_date(r.get('date')),
            str(r.get('contract')),
            str(r.get('rank_type')),
            int(r.get('rank_no')) if r.get('rank_no') is not None else None,
            r.get('member_name'),
            _nullable_float(r.get('volume')),
            _nullable_float(r.get('change')),
            r.get('source_name') or 'cffex_position_rank',
            r.get('run_id'),
        ))
    execute_many("""
        INSERT INTO cffex_position_rank (
            date, contract, rank_type, rank_no, member_name,
            volume, change, source_name, run_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, contract, rank_type, rank_no, member_name) DO UPDATE SET
            volume = EXCLUDED.volume,
            change = EXCLUDED.change,
            source_name = EXCLUDED.source_name,
            run_id = EXCLUDED.run_id
    """, rows)
    return len(rows)


def get_cffex_position_rank(date=None, contract=None, limit=200):
    filters = []
    params = []
    if date is not None:
        filters.append("date = ?")
        params.append(_nullable_norm_date(date))
    if contract is not None:
        filters.append("contract = ?")
        params.append(str(contract))
    if date is None:
        filters.append("date = (SELECT MAX(date) FROM cffex_position_rank)")
    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    params.append(limit)
    return _to_records(query(f"""
        SELECT date, contract, rank_type, rank_no, member_name,
               volume, change, source_name, run_id
        FROM cffex_position_rank
        {where_sql}
        ORDER BY date DESC, contract, rank_type, rank_no NULLS LAST
        LIMIT ?
    """, params))


def _huijin_config_holdings():
    path = os.path.join(BASE_DIR, 'huijin_config.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return (json.load(f) or {}).get('持仓', {}) or {}


def _huijin_codes():
    codes = set(str(c) for c in _huijin_config_holdings().keys())
    if _table_exists('huijin_baseline'):
        rows = _to_records(query("SELECT DISTINCT code FROM huijin_baseline"))
        codes.update(str(r['code']) for r in rows if r.get('code'))
    if _table_exists('huijin_watch_group'):
        rows = _to_records(query("SELECT DISTINCT code FROM huijin_watch_group WHERE is_active = TRUE"))
        codes.update(str(r['code']) for r in rows if r.get('code'))
    return sorted(codes)


def _fund_info(code):
    row = query_one("""
        SELECT code, name, exchange, index_name
        FROM fund
        WHERE code = ?
    """, [str(code)])
    if row:
        return row
    info = (_huijin_config_holdings().get(str(code)) or {})
    return {
        'code': str(code),
        'name': info.get('名称'),
        'exchange': _display_exchange(_code_exchange(code)),
        'index_name': None,
    }


def _audit_for_share(code, date):
    rows = get_daily_snapshot_audit(code=code, date=date, limit=20)
    if rows:
        priority = {'sse_etf_scale': 0, 'szse_etf_scale': 0, 'backfill_sse_etf_scale': 1, 'backfill_szse_etf_scale': 1}
        rows.sort(key=lambda r: priority.get(r.get('source_name'), 9))
        return rows[0]
    return None


def _open_quality_for(code, date=None):
    rows = get_data_quality_issues(code=code, status='open')
    if date is None:
        return rows
    date_s = _nullable_norm_date(date)
    return [r for r in rows if r.get('date') in (None, date_s)]


def _latest_valid_share(code, as_of_date, exchange):
    as_of = _nullable_norm_date(as_of_date)
    rows = _to_records(query("""
        SELECT date, code, total_shares
        FROM daily_snapshot
        WHERE code = ? AND total_shares IS NOT NULL AND date <= ?
          AND strftime(date, '%w') NOT IN ('0', '6')
        ORDER BY date DESC
        LIMIT 40
    """, [str(code), as_of]))
    for row in rows:
        if not is_trading_day(row['date'], exchange):
            continue
        audit = _audit_for_share(code, row['date'])
        return {
            'date': row['date'],
            'total_shares': row.get('total_shares'),
            'audit': audit,
            'stale': row['date'] != as_of,
        }
    return None


def _share_changes(code, share_date, baseline=None):
    """Get share changes over 1, 5, 10, 20, 60 trading days and vs baseline."""
    result = {}
    exchange = _code_exchange(code)

    # Use market_calendar to find past trading day dates
    has_calendar = _table_exists('market_calendar') and query_one("SELECT COUNT(*) AS cnt FROM market_calendar WHERE exchange=? AND is_trading_day=TRUE LIMIT 1", [exchange])
    if has_calendar and has_calendar.get('cnt', 0) > 0:
        past_dates = [r['date'] for r in _to_records(query("""
            SELECT date FROM market_calendar
            WHERE exchange = ? AND is_trading_day = TRUE AND date < ?
            ORDER BY date DESC
            LIMIT 60
        """, [exchange, _nullable_norm_date(share_date)]))]
    else:
        # Fallback: use daily_snapshot with weekend filter
        past_rows = _to_records(query("""
            SELECT date FROM daily_snapshot
            WHERE code = ? AND total_shares IS NOT NULL AND date < ?
              AND strftime(date, '%w') NOT IN ('0', '6')
            ORDER BY date DESC
            LIMIT 60
        """, [str(code), _nullable_norm_date(share_date)]))
        past_dates = [r['date'] for r in past_rows]

    if not past_dates:
        return result

    # Get current shares
    cur_row = query_one("SELECT total_shares FROM daily_snapshot WHERE code=? AND date=?",
                        [str(code), _nullable_norm_date(share_date)])
    cur_shares = cur_row['total_shares'] if cur_row and cur_row.get('total_shares') is not None else None
    if cur_shares is None:
        return result

    offsets = [('1d', 1), ('5d', 5), ('10d', 10), ('20d', 20), ('60d', 60)]
    for label, offset in offsets:
        if len(past_dates) >= offset:
            prev_date = past_dates[offset - 1]
            prev_row = query_one("""
                SELECT total_shares FROM daily_snapshot
                WHERE code=? AND total_shares IS NOT NULL AND date <= ? AND date >= ?::DATE - INTERVAL '10 days'
                ORDER BY date DESC LIMIT 1
            """, [str(code), _nullable_norm_date(prev_date), _nullable_norm_date(prev_date)])
            prev_shares = prev_row['total_shares'] if prev_row else None
            if prev_shares and prev_shares > 0:
                delta = cur_shares - prev_shares
                result[f'share_change_{label}'] = round(delta / 1e4, 2)
                result[f'share_change_ratio_{label}'] = round(delta / prev_shares * 100, 4)

    # Vs baseline (S0)
    if baseline and baseline.get('s0_total_shares'):
        s0 = float(baseline['s0_total_shares'])
        if s0 > 0:
            ratio = cur_shares / s0
            result['vs_baseline_ratio'] = round(ratio, 4)
            result['vs_baseline_pct'] = round((ratio - 1) * 100, 2)

    return result


def _validate_huijin_inputs(code, baseline, share, skip_quality=False, skip_trading_day=False, skip_events=False):
    blockers = []
    warnings = []
    if not baseline:
        blockers.append(_issue(
            'MISSING_VERIFIED_BASELINE',
            'blocker',
            '缺少 verified 且 active 的汇金披露基准',
            code=code,
        ))
        return blockers, warnings

    for field, issue_type in [
        ('s0_total_shares', 'MISSING_S0'),
        ('h0_total_shares', 'MISSING_H0'),
        ('a_ratio', 'MISSING_A'),
    ]:
        if baseline.get(field) is None:
            blockers.append(_issue(issue_type, 'blocker', f'基准缺少 {field}', code=code))
    if baseline.get('verification_status') != 'verified':
        blockers.append(_issue('BASELINE_NOT_VERIFIED', 'blocker', '基准未 verified', code=code))

    if not share:
        blockers.append(_issue('MISSING_S1', 'blocker', '缺少最新有效 ETF 总份额 S1', code=code))
        return blockers, warnings

    if not skip_trading_day and not is_trading_day(share.get('date'), _code_exchange(code)):
        blockers.append(_issue(
            'NON_TRADING_DATE',
            'blocker',
            '最新份额日期不是有效交易日',
            code=code,
            date=share.get('date'),
        ))

    audit = share.get('audit')
    if not audit:
        blockers.append(_issue(
            'MISSING_S1_AUDIT',
            'blocker',
            '用于计算的份额缺少 source/audit 记录',
            code=code,
            date=share.get('date'),
        ))
    else:
        flags = _flag_set(audit.get('quality_flags'))
        if audit.get('normalized_total_shares') is None:
            blockers.append(_issue(
                'MISSING_S1_AUDIT',
                'blocker',
                'source/audit 缺少标准化份额',
                code=code,
                date=share.get('date'),
            ))
        if audit.get('raw_unit') not in ('份', 'shares', 'share'):
            blockers.append(_issue(
                'UNIT_UNVERIFIED',
                'blocker',
                f"份额单位未验证: {audit.get('raw_unit') or '空'}",
                code=code,
                date=share.get('date'),
            ))
        if audit.get('source_date_inferred') or 'SOURCE_DATE_INFERRED' in flags:
            warnings.append(_issue(
                'SOURCE_DATE_INFERRED',
                'warning',
                '份额源日期由交易日历推断',
                code=code,
                date=share.get('date'),
            ))
        for flag in ['SHARE_GAP', 'ABNORMAL_JUMP']:
            if flag in flags:
                warnings.append(_issue(flag, 'warning', f'份额 audit 标记 {flag}', code=code, date=share.get('date')))

    events = []
    if not skip_events and baseline.get('report_date') and share.get('date'):
        events = get_fund_share_events(
            code=code,
            start_date=baseline.get('report_date'),
            end_date=share.get('date'),
            unresolved_only=True,
        )
    if events:
        blockers.append(_issue(
            'UNRESOLVED_SHARE_EVENT',
            'blocker',
            '基准日至计算日之间存在未处理份额事件',
            code=code,
            date=events[0].get('event_date'),
        ))

    if not skip_quality:
        for issue in _open_quality_for(code, share.get('date')):
            target = blockers if issue.get('severity') == 'blocker' else warnings
            target.append(_issue(
                issue.get('issue_type'),
                issue.get('severity'),
                issue.get('message'),
                code=issue.get('code'),
                date=issue.get('date'),
            ))

    return blockers, warnings


def _calculate_huijin_interval(baseline, share):
    s0 = float(baseline['s0_total_shares'])
    h0 = float(baseline['h0_total_shares'])
    a = float(baseline['a_ratio'])
    s1 = float(share['total_shares'])
    b = s1 / s0
    return {
        's0_total_shares': s0,
        'h0_total_shares': h0,
        'a_ratio': a,
        'x0_ratio': 1 - a,
        's1_total_shares': s1,
        'b_ratio': b,
        'y_min': max(0, b - (1 - a)),
        'y_max': b,
    }


def _detect_ten_x_signal(code, as_of_date, lookback=30, baseline_window=20, threshold=10, consecutive=7):
    """Detect if share changes exceed threshold * baseline for N consecutive days."""
    try:
        exchange = _code_exchange(code)
        rows = _to_records(query("""
            SELECT s.date, s.total_shares
            FROM daily_snapshot s
            JOIN market_calendar mc ON mc.date = s.date AND mc.exchange = ? AND mc.is_trading_day = TRUE
            WHERE s.code = ? AND s.total_shares IS NOT NULL AND s.date <= ?
            ORDER BY s.date DESC
            LIMIT ?
        """, [exchange, str(code), _nullable_norm_date(as_of_date), lookback + 5]))
        if len(rows) < lookback:
            return None
        rows.reverse()
        # Calculate absolute daily changes
        abs_changes = []
        for i in range(1, len(rows)):
            if rows[i-1].get('total_shares') and rows[i].get('total_shares'):
                change = abs(float(rows[i]['total_shares']) - float(rows[i-1]['total_shares']))
                abs_changes.append((rows[i]['date'], change))
        if len(abs_changes) < baseline_window + consecutive:
            return None
        # Baseline = median of first `baseline_window` absolute changes
        baseline_values = sorted(c for _, c in abs_changes[-baseline_window-consecutive:-consecutive])
        if not baseline_values:
            return None
        baseline = baseline_values[len(baseline_values) // 2]
        if baseline <= 0:
            return None
        # Check last `consecutive` days
        recent = abs_changes[-consecutive:]
        flagged = [(d, c / baseline) for d, c in recent if c > baseline * threshold]
        return {
            'active': len(flagged) >= consecutive,
            'consecutive_days': len(flagged),
            'baseline_volume': round(baseline, 2),
            'threshold': threshold,
            'current_ratio': round(flagged[-1][1], 1) if flagged else None,
        }
    except Exception:
        return None


def _pool_change_ratio(group_items, change_key, total_shares):
    """Calculate aggregate share change ratio for an ETF pool."""
    total_change = sum(
        i.get(change_key) or 0
        for i in group_items
        if i.get(change_key) is not None
    )
    if total_shares and total_change != 0:
        return round(total_change * 10000 / total_shares, 4)  # 万份→百分比


def get_huijin_overview(as_of_date=None):
    if as_of_date is None:
        as_of_date = get_max_date() or datetime.now().strftime('%Y-%m-%d')
    as_of = _nullable_norm_date(as_of_date)
    group_rows = get_huijin_watch_groups(active_only=True)
    group_by_code = {}
    for row in group_rows:
        group_by_code.setdefault(str(row['code']), []).append(row['group_name'])

    items = []
    for code in _huijin_codes():
        info = _fund_info(code)
        exchange = _code_exchange(code)
        baseline = get_active_huijin_baseline(code, as_of_date=as_of)
        share = _latest_valid_share(code, as_of, exchange)
        blockers, warnings = _validate_huijin_inputs(code, baseline, share)
        interval = None
        if not blockers and baseline and share:
            interval = _calculate_huijin_interval(baseline, share)
        changes = _share_changes(code, share['date'], baseline=baseline) if share else {}
        audit = share.get('audit') if share else None
        items.append({
            'code': code,
            'name': info.get('name'),
            'exchange': info.get('exchange') or _display_exchange(exchange),
            'index_name': info.get('index_name'),
            'watch_groups': group_by_code.get(code, []),
            'status': 'ok' if interval else 'blocked',
            'can_calculate_interval': bool(interval),
            'blockers': blockers,
            'warnings': warnings,
            'baseline': baseline,
            'latest_share': {
                'date': share.get('date') if share else None,
                'total_shares': share.get('total_shares') if share else None,
                'total_shares_亿': round(share.get('total_shares') / 1e8, 4) if share and share.get('total_shares') is not None else None,
                'stale': share.get('stale') if share else None,
                'source_name': audit.get('source_name') if audit else None,
                'source_date': audit.get('source_date') if audit else None,
                'source_date_inferred': audit.get('source_date_inferred') if audit else None,
                'quality_flags': audit.get('quality_flags') if audit else None,
            },
            'share_change_1d': changes.get('share_change_1d'),
            'share_change_5d': changes.get('share_change_5d'),
            'share_change_10d': changes.get('share_change_10d'),
            'share_change_20d': changes.get('share_change_20d'),
            'share_change_60d': changes.get('share_change_60d'),
            'share_change_ratio_1d': changes.get('share_change_ratio_1d'),
            'share_change_ratio_5d': changes.get('share_change_ratio_5d'),
            'share_change_ratio_10d': changes.get('share_change_ratio_10d'),
            'share_change_ratio_20d': changes.get('share_change_ratio_20d'),
            'share_change_ratio_60d': changes.get('share_change_ratio_60d'),
            'vs_baseline_ratio': changes.get('vs_baseline_ratio'),
            'vs_baseline_pct': changes.get('vs_baseline_pct'),
            'interval': interval,
            'interval_note': '相对披露日总份额归一化口径，不代表实时汇金真实持仓' if interval else None,
            'ten_x_signal': _detect_ten_x_signal(code, as_of),
        })

    groups = []
    for group_name in sorted({r['group_name'] for r in group_rows}):
        group_items = [i for i in items if group_name in i.get('watch_groups', [])]
        total_shares = sum(
            i['latest_share']['total_shares'] or 0
            for i in group_items
        ) if group_items else None
        total_s0 = sum(
            (i['interval']['s0_total_shares'] if i.get('interval') else 0) or 0
            for i in group_items
        ) if group_items else None
        groups.append({
            'group_name': group_name,
            'scope_note': 'ETF 池份额观察，不代表单一汇金账户仓位',
            'codes': [i['code'] for i in group_items],
            'ok_count': sum(1 for i in group_items if i['status'] == 'ok'),
            'blocked_count': sum(1 for i in group_items if i['status'] != 'ok'),
            'latest_total_shares': total_shares,
            'total_s0_shares': total_s0,
            'share_change_ratio_1d': _pool_change_ratio(group_items, 'share_change_1d', total_shares),
            'share_change_ratio_5d': _pool_change_ratio(group_items, 'share_change_5d', total_shares),
            'share_change_ratio_10d': _pool_change_ratio(group_items, 'share_change_10d', total_shares),
            'share_change_ratio_20d': _pool_change_ratio(group_items, 'share_change_20d', total_shares),
            'share_change_ratio_60d': _pool_change_ratio(group_items, 'share_change_60d', total_shares),
        })

    ok_count = sum(1 for i in items if i['status'] == 'ok')
    blocked_count = len(items) - ok_count
    warning_count = sum(1 for i in items if i.get('warnings'))
    share_dates = [i['latest_share']['date'] for i in items if i['latest_share'] and i['latest_share'].get('date')]
    latest_share_date = max(share_dates) if share_dates else None

    ten_x_active_count = sum(1 for i in items if i.get('ten_x_signal') and i['ten_x_signal'].get('active'))
    ten_x_active_codes = [i['code'] for i in items if i.get('ten_x_signal') and i['ten_x_signal'].get('active')]

    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'as_of_date': as_of,
        'latest_share_date': latest_share_date,
        'total': len(items),
        'ok_count': ok_count,
        'blocked_count': blocked_count,
        'warning_count': warning_count,
        'ten_x_active_count': ten_x_active_count,
        'ten_x_active_codes': ten_x_active_codes,
        'items': items,
        'groups': groups,
        'disclaimer': 'ETF 份额变化只作为公开数据观察，不等同于中央汇金交易确认。',
    }


def get_huijin_series(code, as_of_date=None, limit=250):
    if as_of_date is None:
        as_of_date = get_max_date() or datetime.now().strftime('%Y-%m-%d')
    as_of = _nullable_norm_date(as_of_date)
    exchange = _code_exchange(code)

    # Use market_calendar if available, else weekday fallback
    has_calendar = _table_exists('market_calendar') and query_one("SELECT COUNT(*) AS cnt FROM market_calendar") and query_one("SELECT COUNT(*) AS cnt FROM market_calendar").get('cnt', 0) > 0

    if has_calendar:
        rows = _to_records(query("""
            SELECT s.date, s.total_shares,
                   a.source_name, a.source_url, a.source_date, a.source_date_inferred,
                   a.raw_unit, a.normalized_total_shares, a.quality_flags
            FROM daily_snapshot s
            LEFT JOIN LATERAL (
                SELECT source_name, source_url, source_date, source_date_inferred,
                       raw_unit, normalized_total_shares, quality_flags
                FROM daily_snapshot_audit a2
                WHERE a2.date = s.date AND a2.code = s.code
                ORDER BY CASE a2.source_name
                    WHEN 'sse_etf_scale' THEN 0
                    WHEN 'szse_etf_scale' THEN 0
                    WHEN 'backfill_sse_etf_scale' THEN 1
                    WHEN 'backfill_szse_etf_scale' THEN 1
                    ELSE 9
                END
                LIMIT 1
            ) a ON TRUE
            WHERE s.code = ? AND s.total_shares IS NOT NULL AND s.date <= ?
              AND EXISTS (SELECT 1 FROM market_calendar mc
                           WHERE mc.date = s.date AND mc.exchange = ? AND mc.is_trading_day = TRUE)
            ORDER BY s.date DESC
            LIMIT ?
        """, [str(code), as_of, exchange, limit]))
    else:
        rows = _to_records(query("""
            SELECT s.date, s.total_shares,
                   a.source_name, a.source_url, a.source_date, a.source_date_inferred,
                   a.raw_unit, a.normalized_total_shares, a.quality_flags
            FROM daily_snapshot s
            LEFT JOIN LATERAL (
                SELECT source_name, source_url, source_date, source_date_inferred,
                       raw_unit, normalized_total_shares, quality_flags
                FROM daily_snapshot_audit a2
                WHERE a2.date = s.date AND a2.code = s.code
                ORDER BY CASE a2.source_name
                    WHEN 'sse_etf_scale' THEN 0
                    WHEN 'szse_etf_scale' THEN 0
                    WHEN 'backfill_sse_etf_scale' THEN 1
                    WHEN 'backfill_szse_etf_scale' THEN 1
                    ELSE 9
                END
                LIMIT 1
            ) a ON TRUE
            WHERE s.code = ? AND s.total_shares IS NOT NULL AND s.date <= ?
            ORDER BY s.date DESC
            LIMIT ?
        """, [str(code), as_of, limit]))
    rows = list(reversed(rows))

    # Filter non-trading days (needed for fallback; belt-and-suspenders for calendar path)
    if not has_calendar:
        rows = [r for r in rows if is_trading_day(r['date'], exchange)]

    # Get quality issues once
    quality_issues = {q['date']: q for q in get_data_quality_issues(code=code, status='open')}

    # Pre-fetch baseline once (all points share the same active baseline)
    baseline = get_active_huijin_baseline(code, as_of_date=as_of)
    baseline_cache = {}

    series = []
    for i, row in enumerate(rows):
        # Get baseline for this date from cache or fetch
        bl_key = row['date']
        if bl_key not in baseline_cache:
            if baseline and baseline.get('disclosure_date') and row['date'] >= baseline['disclosure_date']:
                baseline_cache[bl_key] = baseline
            else:
                baseline_cache[bl_key] = get_active_huijin_baseline(code, as_of_date=row['date'])
        baseline = baseline_cache[bl_key]

        audit = {
            'source_name': row.get('source_name'),
            'source_url': row.get('source_url'),
            'source_date': row.get('source_date'),
            'source_date_inferred': row.get('source_date_inferred'),
            'raw_unit': row.get('raw_unit'),
            'normalized_total_shares': row.get('normalized_total_shares'),
            'quality_flags': row.get('quality_flags'),
        } if row.get('source_name') else None

        share = {'date': row['date'], 'total_shares': row.get('total_shares'), 'audit': audit, 'stale': False}
        blockers, warnings = _validate_huijin_inputs(str(code), baseline, share, skip_quality=True, skip_trading_day=True, skip_events=True)

        # Add quality issue warnings without extra query
        qi = quality_issues.get(row['date'])
        if qi:
            target = blockers if qi.get('severity') == 'blocker' else warnings
            target.append(_issue(qi.get('issue_type'), qi.get('severity'), qi.get('message'), code=code, date=row['date']))

        interval = None
        if not blockers and baseline:
            interval = _calculate_huijin_interval(baseline, share)

        # Compute share changes from in-memory data
        changes = {}
        for label, offset in [('1d', 1), ('5d', 5), ('21d', 21)]:
            prev = rows[i - offset] if i >= offset else None
            if prev and prev.get('total_shares') not in (None, 0):
                delta = row['total_shares'] - prev['total_shares']
                changes[f'share_change_{label}'] = round(delta / 1e4, 2)
                changes[f'share_change_ratio_{label}'] = round(delta / prev['total_shares'] * 100, 4)
            else:
                changes[f'share_change_{label}'] = None
                changes[f'share_change_ratio_{label}'] = None

        series.append({
            'date': row['date'],
            's1_total_shares': row.get('total_shares'),
            'source_name': audit.get('source_name') if audit else None,
            'source_url': audit.get('source_url') if audit else None,
            'source_date': audit.get('source_date') if audit else None,
            'source_date_inferred': audit.get('source_date_inferred') if audit else None,
            'quality_flags': audit.get('quality_flags') if audit else None,
            'share_change_1d': changes.get('share_change_1d'),
            'share_change_5d': changes.get('share_change_5d'),
            'share_change_21d': changes.get('share_change_21d'),
            'share_change_ratio_1d': changes.get('share_change_ratio_1d'),
            'share_change_ratio_5d': changes.get('share_change_ratio_5d'),
            'share_change_ratio_21d': changes.get('share_change_ratio_21d'),
            'status': 'ok' if interval else 'blocked',
            'blockers': blockers,
            'warnings': warnings,
            'baseline_id': baseline.get('baseline_id') if baseline else None,
            'b_ratio': interval.get('b_ratio') if interval else None,
            'y_min': interval.get('y_min') if interval else None,
            'y_max': interval.get('y_max') if interval else None,
        })

    baseline_history = [
        b for b in get_huijin_baselines(code=str(code), active_only=True, verified_only=True)
        if b.get('disclosure_date') and b.get('disclosure_date') <= as_of
    ]

    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'code': str(code),
        'as_of_date': as_of,
        'baseline': get_active_huijin_baseline(code, as_of_date=as_of),
        'baseline_history': baseline_history,
        'events': get_fund_share_events(code=code),
        'series': series,
        'disclaimer': '历史序列使用当日已披露 verified 基准，避免未来函数。',
    }


def _quote_sql(value):
    return "'" + str(value).replace("'", "''") + "'"


def _sql_values(values):
    return ','.join(f"({_quote_sql(v)})" for v in values)


def _issue(issue_type, severity, message, code=None, date=None):
    return {
        'issue_type': issue_type,
        'severity': severity,
        'code': code,
        'date': date,
        'message': message,
    }


def audit_huijin_data(include_persistent=True):
    """Read-only audit for whether current data can support Huijin formulas."""
    cfg_path = os.path.join(BASE_DIR, 'huijin_config.json')
    holdings = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            holdings = (json.load(f) or {}).get('持仓', {}) or {}

    issues = []
    funds = []
    codes = sorted(str(c) for c in holdings.keys())

    snapshot_row = query_one("""
        SELECT COUNT(*) AS rows_count,
               COUNT(DISTINCT code) AS code_count,
               MIN(date) AS min_date,
               MAX(date) AS max_date
        FROM daily_snapshot
    """) or {}

    baseline_table = query_one("""
        SELECT COUNT(*) AS cnt
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = 'huijin_baseline'
    """) or {}
    if baseline_table.get('cnt'):
        baseline_summary = query_one("""
            SELECT COUNT(*) AS total_count,
                   COALESCE(SUM(CASE WHEN verification_status = 'draft' THEN 1 ELSE 0 END), 0) AS draft_count,
                   COALESCE(SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END), 0) AS verified_count,
                   COALESCE(SUM(CASE WHEN verification_status = 'verified' AND is_active THEN 1 ELSE 0 END), 0)
                       AS active_verified_count
            FROM huijin_baseline
        """) or {}
        baseline_rows = _to_records(query("""
            SELECT code,
                   COUNT(*) AS baseline_count,
                   COALESCE(SUM(CASE WHEN verification_status = 'draft' THEN 1 ELSE 0 END), 0) AS draft_count,
                   COALESCE(SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END), 0) AS verified_count,
                   COALESCE(SUM(CASE WHEN verification_status = 'verified' AND is_active THEN 1 ELSE 0 END), 0)
                       AS active_verified_count
            FROM huijin_baseline
            GROUP BY code
        """))
    else:
        baseline_summary = {}
        baseline_rows = []
    baseline_by_code = {str(r['code']): r for r in baseline_rows}

    weekend_rows = _to_records(query("""
        SELECT strftime(date, '%Y-%m-%d') AS date, COUNT(*) AS rows_count
        FROM daily_snapshot
        WHERE total_shares IS NOT NULL AND strftime(date, '%w') IN ('0', '6')
        GROUP BY date
        ORDER BY date DESC
        LIMIT 20
    """))
    for row in weekend_rows:
        issues.append(_issue(
            'NON_TRADING_DATE',
            'blocker',
            f"发现非交易日份额数据 {row['rows_count']} 行，需要核对源日期和落库日期",
            date=row['date'],
        ))

    task_rows = _to_records(query("""
        SELECT task_name, last_run_at, last_status, last_error
        FROM task_status
        WHERE task_name IN ('shares_sse', 'shares_szse')
        ORDER BY task_name
    """))
    for row in task_rows:
        if row.get('last_status') == 'failed':
            issues.append(_issue(
                'SOURCE_FAILED',
                'warning',
                f"{row['task_name']} 最近一次采集失败: {row.get('last_error') or ''}".strip(),
            ))

    if not codes:
        issues.append(_issue(
            'MISSING_BASELINE',
            'blocker',
            '未找到 huijin_config.json 持仓配置，无法建立汇金观察基准',
        ))
    else:
        values_sql = _sql_values(codes)
        codes_sql = ','.join(_quote_sql(c) for c in codes)
        latest_rows = _to_records(query(f"""
            WITH config(code) AS (VALUES {values_sql}),
            latest AS (
                SELECT code, MAX(date) AS max_date
                FROM daily_snapshot
                WHERE total_shares IS NOT NULL
                GROUP BY code
            )
            SELECT c.code,
                   f.name,
                   f.exchange,
                   f.huijin_亿,
                   l.max_date AS latest_share_date,
                   s.total_shares AS latest_total_shares,
                   ROUND(s.total_shares / 1e8, 4) AS latest_total_shares_亿
            FROM config c
            LEFT JOIN fund f ON f.code = c.code
            LEFT JOIN latest l ON l.code = c.code
            LEFT JOIN daily_snapshot s ON s.code = c.code AND s.date = l.max_date
            ORDER BY c.code
        """))
        latest_by_code = {str(r['code']): r for r in latest_rows}

        gap_rows = _to_records(query(f"""
            WITH d AS (
                SELECT code,
                       date,
                       total_shares,
                       LAG(date) OVER (PARTITION BY code ORDER BY date) AS prev_date,
                       LAG(total_shares) OVER (PARTITION BY code ORDER BY date) AS prev_shares
                FROM daily_snapshot
                WHERE code IN ({codes_sql})
                  AND total_shares IS NOT NULL
            )
            SELECT code,
                   MAX(date_diff('day', prev_date, date)) AS max_gap_days,
                   MAX(ABS(total_shares - prev_shares) / NULLIF(prev_shares, 0)) AS max_change_ratio
            FROM d
            WHERE prev_date IS NOT NULL
            GROUP BY code
        """))
        gap_by_code = {str(r['code']): r for r in gap_rows}

        for code in codes:
            info = holdings.get(code, {}) or {}
            configured_holding = info.get('汇金总持股(亿)')
            row = latest_by_code.get(code, {'code': code})
            gap = gap_by_code.get(code, {})
            latest_total = row.get('latest_total_shares')
            fund_name = row.get('name') or info.get('名称')

            fund_status = {
                'code': code,
                'name': fund_name,
                'exchange': row.get('exchange'),
                'configured_huijin_holding_亿': configured_holding,
                'baseline_count': (baseline_by_code.get(code) or {}).get('baseline_count', 0),
                'verified_baseline_count': (baseline_by_code.get(code) or {}).get('verified_count', 0),
                'active_verified_baseline_count': (baseline_by_code.get(code) or {}).get('active_verified_count', 0),
                'latest_share_date': row.get('latest_share_date'),
                'latest_total_shares_亿': row.get('latest_total_shares_亿'),
                'max_gap_days': gap.get('max_gap_days'),
                'max_change_ratio': gap.get('max_change_ratio'),
                'can_calculate_interval': False,
            }
            funds.append(fund_status)

            active_verified_count = (baseline_by_code.get(code) or {}).get('active_verified_count', 0)
            if active_verified_count == 0:
                if configured_holding is None:
                    issues.append(_issue(
                        'MISSING_H0',
                        'blocker',
                        'huijin_config.json 确认持有但缺少汇金持有份额 H0',
                        code=code,
                    ))
                else:
                    issues.append(_issue(
                        'MISSING_S0',
                        'blocker',
                        '当前配置缺少披露日总份额 S0 和披露比例 A，不能计算汇金区间',
                        code=code,
                    ))
                issues.append(_issue(
                    'MISSING_VERIFIED_BASELINE',
                    'blocker',
                    '缺少 verified 且 active 的汇金披露基准；huijin_config/draft 只能作为人工核验线索',
                    code=code,
                ))

            if latest_total is None:
                issues.append(_issue(
                    'MISSING_S1',
                    'blocker',
                    '缺少最新有效 ETF 总份额 S1',
                    code=code,
                ))
            elif configured_holding is not None and latest_total < float(configured_holding) * 1e8:
                issues.append(_issue(
                    'CURRENT_SHARES_BELOW_CONFIG_HOLDING',
                    'warning',
                    '最新总份额低于配置中的汇金披露持有份额；这不必然是单位错误，但必须回到 S0/A 基准核验',
                    code=code,
                    date=row.get('latest_share_date'),
                ))

            max_gap = gap.get('max_gap_days')
            if max_gap is not None and max_gap > 10:
                issues.append(_issue(
                    'SHARE_GAP',
                    'warning',
                    f'份额序列存在最长 {max_gap} 天间隔，需要补齐或标记断档',
                    code=code,
                ))

            max_change = gap.get('max_change_ratio')
            if max_change is not None and max_change > 0.3:
                issues.append(_issue(
                    'ABNORMAL_JUMP',
                    'warning',
                    f'份额序列存在超过 {max_change:.2%} 的相邻跳变，需要核对源数据或份额事件',
                    code=code,
                ))

    persistent_issues = []
    if include_persistent and _table_exists('data_quality_issue'):
        persistent_issues = get_data_quality_issues(status='open', limit=1000)

    severity_counts = {}
    for item in issues:
        sev = item['severity']
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    persistent_counts = {}
    for item in persistent_issues:
        sev = item.get('severity')
        persistent_counts[sev] = persistent_counts.get(sev, 0) + 1

    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'summary': {
            'snapshot_rows': snapshot_row.get('rows_count'),
            'snapshot_codes': snapshot_row.get('code_count'),
            'snapshot_min_date': snapshot_row.get('min_date'),
            'snapshot_max_date': snapshot_row.get('max_date'),
            'huijin_config_codes': len(codes),
            'huijin_config_with_holding': sum(
                1 for v in holdings.values()
                if (v or {}).get('汇金总持股(亿)') is not None
            ),
            'huijin_baseline_total': baseline_summary.get('total_count'),
            'huijin_baseline_draft': baseline_summary.get('draft_count'),
            'huijin_baseline_verified': baseline_summary.get('verified_count'),
            'huijin_baseline_active_verified': baseline_summary.get('active_verified_count'),
            'issues_total': len(issues),
            'issues_by_severity': severity_counts,
            'persistent_open_issues_total': len(persistent_issues),
            'persistent_open_issues_by_severity': persistent_counts,
        },
        'issues': issues,
        'persistent_issues': persistent_issues,
        'funds': funds,
    }


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


def get_task_status_all(read_only=True):
    return _to_records(query("""
        SELECT task_name, display_name, schedule_cron, enabled,
               last_run_at, last_status, last_duration, last_error, next_run_at
        FROM task_status ORDER BY task_name
    """, read_only=read_only))


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


def get_task_history(task_name, limit=20, read_only=True):
    return _to_records(query("""
        SELECT run_at AS last_run_at, status AS last_status,
               duration AS last_duration, error AS last_error, records_count
        FROM task_history
        WHERE task_name = ?
        ORDER BY run_at DESC LIMIT ?
    """, [task_name, limit], read_only=read_only))


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
    seed_count = seed_huijin_baselines_from_config()
    if seed_count:
        print(f"[migrate] seeded {seed_count} huijin draft baselines")
    group_count = seed_huijin_watch_groups()
    if group_count:
        print(f"[migrate] seeded {group_count} huijin watch groups")
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
    try:
        return _to_records(query("""
            SELECT date, open, high, low, close, volume, amount, amplitude, turnover
            FROM daily_kline
            WHERE code = ? AND close IS NOT NULL
            ORDER BY date DESC
            LIMIT ?
        """, [code, limit]))
    except Exception:
        return []


def get_codes_with_kline():
    df = query("SELECT DISTINCT code FROM daily_kline")
    return set(df['code'].tolist())


# ─── sector_fund_flow ─────────────────────────────────────────

def upsert_sector_fund_flow(records, period='1d'):
    if not records:
        return
    sql = """
        INSERT INTO sector_fund_flow (date, sector_name, period, net_main, net_super_large, net_large, net_medium, net_small)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, sector_name, period) DO UPDATE SET
            net_main        = COALESCE(EXCLUDED.net_main,        sector_fund_flow.net_main),
            net_super_large = COALESCE(EXCLUDED.net_super_large, sector_fund_flow.net_super_large),
            net_large       = COALESCE(EXCLUDED.net_large,       sector_fund_flow.net_large),
            net_medium      = COALESCE(EXCLUDED.net_medium,      sector_fund_flow.net_medium),
            net_small       = COALESCE(EXCLUDED.net_small,       sector_fund_flow.net_small)
    """
    rows = [(d, s, period, nm, nsl, nl, nmd, ns) for d, s, nm, nsl, nl, nmd, ns in records]
    execute_many(sql, rows)


def query_latest_sector_flow(period='1d'):
    try:
        # Try direct data first
        if period != '1d':
            direct = _to_records(query("""
                SELECT sector_name, net_main, net_super_large, net_large, net_medium, net_small
                FROM sector_fund_flow
                WHERE period = ? AND date = (SELECT MAX(date) FROM sector_fund_flow WHERE period = ?)
                ORDER BY net_main DESC
            """, [period, period]))
            if direct:
                return {'data': direct, 'actual_days': len(direct) and 1}

        # Fallback: 1d or aggregation from daily data
        if period == '1d':
            rows = _to_records(query("""
                SELECT sector_name, net_main, net_super_large, net_large, net_medium, net_small
                FROM sector_fund_flow
                WHERE period = '1d' AND date = (SELECT MAX(date) FROM sector_fund_flow WHERE period = '1d')
                ORDER BY net_main DESC
            """))
            return {'data': rows, 'actual_days': 1 if rows else 0}
        ndays = {'3d': 3, '5d': 5, '10d': 10, '20d': 20}.get(period, 3)
        actual = query_one(f"""
            SELECT COUNT(DISTINCT date) AS cnt FROM sector_fund_flow
            WHERE period = '1d' AND date IN (
                SELECT DISTINCT date FROM sector_fund_flow
                WHERE period = '1d' ORDER BY date DESC LIMIT {ndays}
            )
        """)
        actual_days = actual['cnt'] if actual else 0
        rows = _to_records(query(f"""
            WITH recent AS (
                SELECT DISTINCT date FROM sector_fund_flow
                WHERE period = '1d' ORDER BY date DESC LIMIT {ndays}
            )
            SELECT
                sector_name,
                SUM(net_main) AS net_main,
                SUM(net_super_large) AS net_super_large,
                SUM(net_large) AS net_large,
                SUM(net_medium) AS net_medium,
                SUM(net_small) AS net_small
            FROM sector_fund_flow
            WHERE period = '1d' AND date IN (SELECT date FROM recent)
            GROUP BY sector_name
            ORDER BY net_main DESC
        """))
        return {'data': rows, 'actual_days': actual_days}
    except Exception:
        return {'data': [], 'actual_days': 0}


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
