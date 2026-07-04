"""
Backfill historical NAV data using THS API (one call = ALL ETFs for a date).
Strategy: weekly sampling for 2 years (~100 calls total)
Price history: still blocked, skip for now
"""
import sys, os, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import akshare as ak
import pandas as pd
from db import execute_many, query


def trading_weeks(start='2024-07-01', end='2026-07-03'):
    """Generate weekly trading dates (every Monday)."""
    s = datetime.strptime(start, '%Y-%m-%d')
    e = datetime.strptime(end, '%Y-%m-%d')
    dates = []
    d = s
    while d <= e:
        if d.weekday() < 5:
            dates.append(d.strftime('%Y%m%d'))
        d += timedelta(days=7)
    return dates


def main():
    dates = trading_weeks()
    total = len(dates)
    print(f'Backfilling NAV for {total} weekly dates (2024-07 ~ 2026-07)')
    print(f'Source: fund_etf_spot_ths (one call = ALL ETFs per date)')
    print()

    t0 = time.time()
    done = 0
    total_rows = 0

    for date_str in dates:
        try:
            df = ak.fund_etf_spot_ths(date=date_str)
        except Exception as e:
            print(f'  [{date_str}] FAIL: {e}')
            continue

        today_ymd = datetime.now().strftime('%Y-%m-%d')
        rows = []
        for _, r in df.iterrows():
            code = str(r['基金代码'])
            nav = float(r['当前-单位净值']) if pd.notna(r['当前-单位净值']) else None
            nav_date = str(r['最新-交易日']) if pd.notna(r['最新-交易日']) else None
            if nav and nav_date and nav_date[:4].isdigit():
                d = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
                rows.append((d, code, nav, d))

        if rows:
            sql = """
                INSERT INTO daily_snapshot (date, code, total_shares, price, price_change_pct, turnover, iopv, discount_rt, nav, nav_date)
                VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
                ON CONFLICT (date, code) DO UPDATE SET
                    nav = COALESCE(EXCLUDED.nav, daily_snapshot.nav),
                    nav_date = COALESCE(EXCLUDED.nav_date, daily_snapshot.nav_date)
            """
            # Write in batches of 500
            for i in range(0, len(rows), 500):
                execute_many(sql, rows[i:i+500])
            total_rows += len(rows)

        done += 1
        elapsed = time.time() - t0
        rate = done / elapsed
        eta = (total - done) / rate
        print(f'  [{done}/{total}] {date_str}: {len(rows)} NAV records, {elapsed:.0f}s/{eta:.0f}s', flush=True)

    elapsed = time.time() - t0
    print(f'\nDone! {total} dates in {elapsed:.0f}s')
    print(f'Total NAV rows: {total_rows}')

    # Summary
    r = query('SELECT COUNT(*) as c FROM daily_snapshot WHERE nav IS NOT NULL').iloc[0]['c']
    r2 = query('SELECT MIN(date) as d1, MAX(date) as d2 FROM daily_snapshot WHERE nav IS NOT NULL')
    d1 = r2.iloc[0][0]
    d2 = r2.iloc[0][1]
    print(f'Total records with NAV: {r}')
    print(f'NAV date range: {d1} ~ {d2}')
    print()
    print('NOTE: Price history still unavailable (push2his blocked)')
    print('Current/latest prices available from spot task.')


if __name__ == '__main__':
    main()