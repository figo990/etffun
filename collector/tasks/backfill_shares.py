"""
Backfill historical SHARES data to align with NAV (2024-07 ~ 2026-07).
SSE: fund_etf_scale_sse(date) - one call per date, ~550-820 ETFs
SZSE: fund_scale_daily_szse(start, end, 'ETF') - batch by month, ~1000 ETFs/date

Usage:
  python -m collector.tasks.backfill_shares
  python -m collector.tasks.backfill_shares --repair-huijin-audit --start 2025-12-31
  python -m collector.tasks.backfill_shares --fill-huijin-missing-shares --start 2026-04-07 --end 2026-07-01
"""
import argparse
import sys, os, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import akshare as ak
import pandas as pd
from db import (
    execute_many, query,
    create_data_source_run, finish_data_source_run, upsert_daily_snapshot_audit,
)


def trading_dates(start='2024-07-01', end='2026-07-03'):
    s = datetime.strptime(start, '%Y-%m-%d')
    e = datetime.strptime(end, '%Y-%m-%d')
    dates = []
    d = s
    while d <= e:
        if d.weekday() < 5:
            dates.append(d.strftime('%Y%m%d'))
        d += timedelta(days=1)
    return dates


def shares_match_for_audit(local_shares, source_shares, abs_tolerance=1.0, rel_tolerance=1e-7):
    if local_shares is None or source_shares is None:
        return False
    local = float(local_shares)
    source = float(source_shares)
    if local <= 0 or source <= 0:
        return False
    return abs(local - source) <= max(abs_tolerance, abs(local) * rel_tolerance)


def _norm_ymd(value):
    if isinstance(value, datetime):
        return value.strftime('%Y%m%d')
    text = str(value)[:10]
    return text.replace('-', '')


def _norm_date(value):
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    text = str(value)[:10]
    if len(text) == 8 and text.isdigit():
        return f'{text[:4]}-{text[4:6]}-{text[6:8]}'
    return text.replace('/', '-')


def _chunks(values, size):
    for i in range(0, len(values), size):
        yield values[i:i + size]


def _repair_targets(start=None, end=None, codes=None):
    filters = [
        "b.verification_status = 'verified'",
        "b.is_active = TRUE",
        "b.disclosure_date IS NOT NULL",
        "s.date >= b.disclosure_date",
        "s.total_shares IS NOT NULL",
        "strftime(s.date, '%w') NOT IN ('0', '6')",
        """
        NOT EXISTS (
            SELECT 1 FROM daily_snapshot_audit a
            WHERE a.date = s.date AND a.code = s.code
              AND a.source_name IN (
                  'sse_etf_scale', 'szse_etf_scale',
                  'backfill_sse_etf_scale', 'backfill_szse_etf_scale'
              )
        )
        """,
    ]
    params = []
    if start:
        filters.append("s.date >= ?")
        params.append(_norm_date(start))
    if end:
        filters.append("s.date <= ?")
        params.append(_norm_date(end))
    if codes:
        placeholders = ','.join('?' for _ in codes)
        filters.append(f"s.code IN ({placeholders})")
        params.extend(str(c) for c in codes)
    where_sql = " AND ".join(filters)
    return query(f"""
        SELECT s.date, s.code, s.total_shares
        FROM daily_snapshot s
        JOIN huijin_baseline b ON b.code = s.code
        WHERE {where_sql}
        ORDER BY s.date, s.code
    """, params)


def _missing_share_targets(start=None, end=None, codes=None):
    filters = [
        "b.verification_status = 'verified'",
        "b.is_active = TRUE",
        "b.disclosure_date IS NOT NULL",
        "mc.date >= b.disclosure_date",
        "mc.is_trading_day = TRUE",
    ]
    params = []
    if start:
        filters.append("mc.date >= ?")
        params.append(_norm_date(start))
    if end:
        filters.append("mc.date <= ?")
        params.append(_norm_date(end))
    if codes:
        placeholders = ','.join('?' for _ in codes)
        filters.append(f"b.code IN ({placeholders})")
        params.extend(str(c) for c in codes)
    where_sql = " AND ".join(filters)
    return query(f"""
        WITH baseline_codes AS (
            SELECT code,
                   CASE WHEN starts_with(code, '5') THEN 'SSE' ELSE 'SZSE' END AS exchange,
                   disclosure_date
            FROM huijin_baseline b
            WHERE b.verification_status = 'verified' AND b.is_active = TRUE
        )
        SELECT c.code, c.exchange, mc.date
        FROM baseline_codes c
        JOIN market_calendar mc ON mc.exchange = c.exchange
        LEFT JOIN daily_snapshot s
          ON s.code = c.code AND s.date = mc.date AND s.total_shares IS NOT NULL
        JOIN huijin_baseline b ON b.code = c.code AND b.verification_status = 'verified' AND b.is_active = TRUE
        WHERE {where_sql}
          AND s.code IS NULL
        ORDER BY mc.date, c.code
    """, params)


def fill_huijin_missing_shares(start=None, end=None, codes=None, dry_run=False, batch_size=20):
    """Fill missing Huijin ETF share rows after verified disclosure dates."""
    code_filter = [str(c).strip() for c in (codes or []) if str(c).strip()]
    targets_df = _missing_share_targets(start=start, end=end, codes=code_filter or None)
    if targets_df.empty:
        print('No Huijin share rows require filling')
        return {'targets': 0, 'matched': 0, 'written': 0, 'missing': 0}

    targets = {( _norm_date(r['date']), str(r['code']) ): str(r['exchange'])
               for _, r in targets_df.iterrows()}
    dates = sorted({date for date, _ in targets})
    run_id = create_data_source_run('backfill_huijin_missing_shares', 'verified_historical_etf_scale')
    snap_rows = []
    audit_rows = []
    missing = []

    try:
        sse_dates = [d for d in dates if any(ex == 'SSE' for (dd, _), ex in targets.items() if dd == d)]
        for idx, date in enumerate(sse_dates, 1):
            ymd = _norm_ymd(date)
            try:
                df = ak.fund_etf_scale_sse(date=ymd)
            except Exception as exc:
                print(f'  [SSE] {date} FAIL: {exc}', flush=True)
                for key, ex in targets.items():
                    if key[0] == date and ex == 'SSE':
                        missing.append(key)
                continue
            source = {}
            for _, r in df.iterrows():
                code = str(r.get('基金代码'))
                shares = float(r.get('基金份额')) if pd.notna(r.get('基金份额')) else None
                if shares:
                    source[code] = shares
            for (row_date, code), ex in targets.items():
                if row_date != date or ex != 'SSE':
                    continue
                shares = source.get(code)
                if shares is None:
                    missing.append((row_date, code))
                    continue
                snap_rows.append((row_date, code, shares))
                audit_rows.append({
                    'date': row_date,
                    'code': code,
                    'source_name': 'backfill_sse_etf_scale',
                    'source_url': f'akshare.fund_etf_scale_sse(date={ymd})',
                    'source_date': row_date,
                    'source_date_inferred': False,
                    'raw_total_shares': shares,
                    'raw_unit': '份',
                    'normalized_total_shares': shares,
                    'run_id': run_id,
                    'quality_flags': '',
                })
            if idx % 20 == 0 or idx == len(sse_dates):
                print(f'  [SSE] {idx}/{len(sse_dates)} dates, matched={len(snap_rows)}', flush=True)

        szse_dates = [d for d in dates if any(ex == 'SZSE' for (dd, _), ex in targets.items() if dd == d)]
        for chunk in _chunks(szse_dates, batch_size):
            s_ymd = _norm_ymd(chunk[0])
            e_ymd = _norm_ymd(chunk[-1])
            try:
                df = ak.fund_scale_daily_szse(start_date=s_ymd, end_date=e_ymd, symbol='ETF')
            except Exception as exc:
                print(f'  [SZSE] {chunk[0]}~{chunk[-1]} FAIL: {exc}', flush=True)
                for key, ex in targets.items():
                    if key[0] in set(chunk) and ex == 'SZSE':
                        missing.append(key)
                continue
            source = {}
            for _, r in df.iterrows():
                date = _norm_date(r.get('日期'))
                code = str(r.get('基金代码'))
                shares = float(r.get('基金份额')) if pd.notna(r.get('基金份额')) else None
                if shares:
                    source[(date, code)] = shares
            for (date, code), ex in targets.items():
                if date not in set(chunk) or ex != 'SZSE':
                    continue
                shares = source.get((date, code))
                if shares is None:
                    missing.append((date, code))
                    continue
                snap_rows.append((date, code, shares))
                audit_rows.append({
                    'date': date,
                    'code': code,
                    'source_name': 'backfill_szse_etf_scale',
                    'source_url': f'akshare.fund_scale_daily_szse(start_date={s_ymd}, end_date={e_ymd}, symbol=ETF)',
                    'source_date': date,
                    'source_date_inferred': False,
                    'raw_total_shares': shares,
                    'raw_unit': '份',
                    'normalized_total_shares': shares,
                    'run_id': run_id,
                    'quality_flags': '',
                })
            print(f'  [SZSE] {chunk[0]}~{chunk[-1]} rows={len(df)}, matched={len(snap_rows)}', flush=True)

        written = 0
        if snap_rows and not dry_run:
            sql = """
                INSERT INTO daily_snapshot (
                    date, code, total_shares, price, price_change_pct, turnover,
                    iopv, discount_rt, nav, nav_date
                )
                VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
                ON CONFLICT (date, code) DO UPDATE SET
                    total_shares = EXCLUDED.total_shares
            """
            for chunk in _chunks(snap_rows, 500):
                execute_many(sql, chunk)
            for chunk in _chunks(audit_rows, 500):
                written += upsert_daily_snapshot_audit(chunk)
        finish_data_source_run(run_id, 'success', written)
        result = {
            'targets': len(targets),
            'matched': len(snap_rows),
            'written': written,
            'missing': len(missing),
        }
        print(f"Huijin missing shares fill: {result}")
        if missing[:10]:
            print('First missing:', missing[:10])
        return result
    except Exception as exc:
        finish_data_source_run(run_id, 'failed', len(snap_rows), str(exc))
        raise


def repair_huijin_verified_audit(start=None, end=None, codes=None, dry_run=False, batch_size=20):
    """Verify and add exchange-source audit rows for Huijin backtest samples.

    Existing legacy rows are not relabeled. A backfill audit row is written only
    when the public source value matches the local S1 for the same code/date.
    """
    code_filter = [str(c).strip() for c in (codes or []) if str(c).strip()]
    targets_df = _repair_targets(start=start, end=end, codes=code_filter or None)
    if targets_df.empty:
        print('No Huijin audit rows require repair')
        return {'targets': 0, 'matched': 0, 'written': 0, 'mismatched': 0, 'missing': 0}

    targets = {}
    for _, row in targets_df.iterrows():
        date = _norm_date(row['date'])
        code = str(row['code'])
        targets[(date, code)] = float(row['total_shares'])

    dates = sorted({date for date, _ in targets})
    sse_dates = [d for d in dates if any(code.startswith('5') for dd, code in targets if dd == d)]
    szse_dates = [d for d in dates if any(code.startswith('1') for dd, code in targets if dd == d)]

    run_id = create_data_source_run('backfill_huijin_audit', 'verified_historical_etf_scale')
    audit_rows = []
    mismatches = []
    missing = []

    try:
        for idx, date in enumerate(sse_dates, 1):
            ymd = _norm_ymd(date)
            try:
                df = ak.fund_etf_scale_sse(date=ymd)
            except Exception as exc:
                print(f'  [SSE] {date} FAIL: {exc}', flush=True)
                for key in [k for k in targets if k[0] == date and k[1].startswith('5')]:
                    missing.append(key)
                continue
            source = {}
            for _, r in df.iterrows():
                code = str(r.get('基金代码'))
                shares = float(r.get('基金份额')) if pd.notna(r.get('基金份额')) else None
                if shares:
                    source[code] = shares
            for key, local_shares in targets.items():
                row_date, code = key
                if row_date != date or not code.startswith('5'):
                    continue
                source_shares = source.get(code)
                if source_shares is None:
                    missing.append(key)
                    continue
                if shares_match_for_audit(local_shares, source_shares):
                    audit_rows.append({
                        'date': date,
                        'code': code,
                        'source_name': 'backfill_sse_etf_scale',
                        'source_url': f'akshare.fund_etf_scale_sse(date={ymd})',
                        'source_date': date,
                        'source_date_inferred': False,
                        'raw_total_shares': source_shares,
                        'raw_unit': '份',
                        'normalized_total_shares': source_shares,
                        'run_id': run_id,
                        'quality_flags': '',
                    })
                else:
                    mismatches.append((date, code, local_shares, source_shares))
            if idx % 20 == 0 or idx == len(sse_dates):
                print(f'  [SSE] {idx}/{len(sse_dates)} dates, matched={len(audit_rows)}', flush=True)

        for chunk in _chunks(szse_dates, batch_size):
            s_ymd = _norm_ymd(chunk[0])
            e_ymd = _norm_ymd(chunk[-1])
            try:
                df = ak.fund_scale_daily_szse(start_date=s_ymd, end_date=e_ymd, symbol='ETF')
            except Exception as exc:
                print(f'  [SZSE] {chunk[0]}~{chunk[-1]} FAIL: {exc}', flush=True)
                for key in [k for k in targets if k[0] in set(chunk) and k[1].startswith('1')]:
                    missing.append(key)
                continue
            source = {}
            for _, r in df.iterrows():
                date = _norm_date(r.get('日期'))
                code = str(r.get('基金代码'))
                shares = float(r.get('基金份额')) if pd.notna(r.get('基金份额')) else None
                if shares:
                    source[(date, code)] = shares
            for key, local_shares in targets.items():
                date, code = key
                if date not in set(chunk) or not code.startswith('1'):
                    continue
                source_shares = source.get(key)
                if source_shares is None:
                    missing.append(key)
                    continue
                if shares_match_for_audit(local_shares, source_shares):
                    audit_rows.append({
                        'date': date,
                        'code': code,
                        'source_name': 'backfill_szse_etf_scale',
                        'source_url': f'akshare.fund_scale_daily_szse(start_date={s_ymd}, end_date={e_ymd}, symbol=ETF)',
                        'source_date': date,
                        'source_date_inferred': False,
                        'raw_total_shares': source_shares,
                        'raw_unit': '份',
                        'normalized_total_shares': source_shares,
                        'run_id': run_id,
                        'quality_flags': '',
                    })
                else:
                    mismatches.append((date, code, local_shares, source_shares))
            print(f'  [SZSE] {chunk[0]}~{chunk[-1]} rows={len(df)}, matched={len(audit_rows)}', flush=True)

        written = 0
        if audit_rows and not dry_run:
            for chunk in _chunks(audit_rows, 500):
                written += upsert_daily_snapshot_audit(chunk)
        finish_data_source_run(run_id, 'success', written)
        result = {
            'targets': len(targets),
            'matched': len(audit_rows),
            'written': written,
            'mismatched': len(mismatches),
            'missing': len(missing),
        }
        print(f"Huijin audit repair: {result}")
        if mismatches[:10]:
            print('First mismatches:', mismatches[:10])
        if missing[:10]:
            print('First missing:', missing[:10])
        return result
    except Exception as exc:
        finish_data_source_run(run_id, 'failed', len(audit_rows), str(exc))
        raise


def main():
    run_id = create_data_source_run('backfill_shares', 'historical_etf_scale')
    all_dates = trading_dates()
    existing = set()
    df = query("SELECT DISTINCT strftime(date, '%Y%m%d') as d FROM daily_snapshot WHERE total_shares IS NOT NULL")
    for _, r in df.iterrows():
        existing.add(r['d'])
    
    dates = [d for d in all_dates if d not in existing]
    if not dates:
        print('All dates already have shares data')
        finish_data_source_run(run_id, 'success', 0)
        return

    total = len(dates)
    print(f'Backfilling shares for {total} dates')
    print(f'  SSE: per-date call ({total} calls)')
    print(f'  SZSE: monthly batch ({(total // 20) + 1} calls)')
    print()

    t0 = time.time()
    total_rows = 0

    try:
        # Pre-fetch SZSE data in monthly batches
        szse_cache = {}
        batch_start = 0
        while batch_start < total:
            batch_end = min(batch_start + 20, total)
            s_date = dates[batch_start]
            e_date = dates[batch_end - 1]
            try:
                szse = ak.fund_scale_daily_szse(start_date=s_date, end_date=e_date, symbol='ETF')
                for _, r in szse.iterrows():
                    rd = str(r['日期'])[:10]
                    code = str(r['基金代码'])
                    shares = float(r['基金份额']) if pd.notna(r['基金份额']) else None
                    if shares:
                        rd_norm = rd.replace('-', '')
                        if rd_norm not in szse_cache:
                            szse_cache[rd_norm] = []
                        szse_cache[rd_norm].append((rd, code, shares))
                print(f'  [SZSE] {s_date}~{e_date}: {len(szse)} rows', flush=True)
            except Exception as e:
                print(f'  [SZSE] {s_date}~{e_date} FAIL: {e}', flush=True)
            batch_start += 20

        # Process each date
        for i, date_str in enumerate(dates):
            d = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
            rows = []
            audit_rows = []

            # SSE
            try:
                sse = ak.fund_etf_scale_sse(date=date_str)
                for _, r in sse.iterrows():
                    code = str(r['基金代码'])
                    shares = float(r['基金份额']) if pd.notna(r['基金份额']) else None
                    if shares:
                        rows.append((d, code, shares))
                        audit_rows.append({
                            'date': d,
                            'code': code,
                            'source_name': 'backfill_sse_etf_scale',
                            'source_url': f'akshare.fund_etf_scale_sse(date={date_str})',
                            'source_date': d,
                            'source_date_inferred': False,
                            'raw_total_shares': shares,
                            'raw_unit': '份',
                            'normalized_total_shares': shares,
                            'run_id': run_id,
                            'quality_flags': '',
                        })
            except Exception as e:
                print(f'  [{date_str}] SSE error: {e}')

            # SZSE from cache
            if date_str in szse_cache:
                for rd, code, shares in szse_cache[date_str]:
                    rows.append((rd, code, shares))
                    audit_rows.append({
                        'date': rd,
                        'code': code,
                        'source_name': 'backfill_szse_etf_scale',
                        'source_url': 'akshare.fund_scale_daily_szse(symbol=ETF)',
                        'source_date': rd,
                        'source_date_inferred': False,
                        'raw_total_shares': shares,
                        'raw_unit': '份',
                        'normalized_total_shares': shares,
                        'run_id': run_id,
                        'quality_flags': '',
                    })

            if rows:
                sql = """
                    INSERT INTO daily_snapshot (date, code, total_shares, price, price_change_pct, turnover, iopv, discount_rt, nav, nav_date)
                    VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
                    ON CONFLICT (date, code) DO UPDATE SET
                        total_shares = COALESCE(EXCLUDED.total_shares, daily_snapshot.total_shares)
                """
                # Write in batches of 500
                for j in range(0, len(rows), 500):
                    execute_many(sql, rows[j:j+500])
                for j in range(0, len(audit_rows), 500):
                    upsert_daily_snapshot_audit(audit_rows[j:j+500])
                total_rows += len(rows)

            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            if (i + 1) % 20 == 0 or i == total - 1:
                print(f'  [{i+1}/{total}] {date_str}: {len(rows)} shares, {elapsed:.0f}s/{eta:.0f}s', flush=True)

        elapsed = time.time() - t0
        print(f'\nDone! {total} dates in {elapsed:.0f}s')
        print(f'Total share rows: {total_rows}')

        r = query('SELECT COUNT(*) as c FROM daily_snapshot WHERE total_shares IS NOT NULL').iloc[0]['c']
        r2 = query('SELECT MIN(date) as d1, MAX(date) as d2 FROM daily_snapshot WHERE total_shares IS NOT NULL')
        r3 = query('SELECT COUNT(*) as c FROM daily_snapshot WHERE total_shares IS NOT NULL AND nav IS NOT NULL').iloc[0]['c']
        print(f'Records with shares: {r}')
        print(f'Shares range: {r2.iloc[0]["d1"]} ~ {r2.iloc[0]["d2"]}')
        print(f'Overlap (shares + nav): {r3}')
        finish_data_source_run(run_id, 'success', total_rows)
    except Exception as e:
        finish_data_source_run(run_id, 'failed', total_rows, str(e))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repair-huijin-audit', action='store_true',
                        help='verify and add exchange backfill audit rows for Huijin backtest samples')
    parser.add_argument('--fill-huijin-missing-shares', action='store_true',
                        help='fill missing Huijin ETF share rows from public exchange sources')
    parser.add_argument('--start', default=None)
    parser.add_argument('--end', default=None)
    parser.add_argument('--codes', default=None, help='comma-separated ETF codes')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.fill_huijin_missing_shares:
        fill_huijin_missing_shares(
            start=args.start,
            end=args.end,
            codes=args.codes.split(',') if args.codes else None,
            dry_run=args.dry_run,
        )
    elif args.repair_huijin_audit:
        repair_huijin_verified_audit(
            start=args.start,
            end=args.end,
            codes=args.codes.split(',') if args.codes else None,
            dry_run=args.dry_run,
        )
    else:
        main()
