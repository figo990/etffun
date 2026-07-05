"""
Backfill historical SHARES data to align with NAV (2024-07 ~ 2026-07).
SSE: fund_etf_scale_sse(date) - one call per date, ~550-820 ETFs
SZSE: fund_scale_daily_szse(start, end, 'ETF') - batch by month, ~1000 ETFs/date

Usage: python -m collector.tasks.backfill_shares
"""
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
    main()
