"""一次性回填历史K线数据（手动运行）"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ['PYTHONUNBUFFERED'] = '1'

import akshare as ak
import pandas as pd
import time
from datetime import datetime
from db import upsert_kline, get_all_codes, get_codes_with_kline, execute


BATCH_SIZE = 30
API_DELAY = 0.5
RETRY_DELAY = 3
START_DATE = '2024-01-01'
END_DATE = datetime.now().strftime('%Y-%m-%d')


def backfill_kline():
    all_codes = get_all_codes()
    existing = get_codes_with_kline()
    todo = [c for c in all_codes if len(c) == 6 and c not in existing]
    print(f"Total ETFs: {len(all_codes)}, already have: {len(existing)}, to backfill: {len(todo)}")

    total_rows = 0
    batch = []
    errors = 0
    for i, code in enumerate(todo):
        for attempt in range(3):
            try:
                df = ak.fund_etf_hist_em(symbol=code, period='daily',
                                         start_date=START_DATE, end_date=END_DATE, adjust='')
                break
            except Exception:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
        else:
            errors += 1
            print(f"  [{i+1}/{len(todo)}] {code} ERROR after 3 retries")
            continue

        if df is None or df.empty:
            print(f"  [{i+1}/{len(todo)}] {code} empty")
            continue

        rows = []
        for _, row in df.iterrows():
            try:
                d = row['日期']
                if isinstance(d, pd.Timestamp):
                    d = d.strftime('%Y-%m-%d')
                else:
                    d = str(d)[:10]
            except Exception:
                continue
            rows.append((
                d, code,
                float(row.get('开盘', 0) or 0),
                float(row.get('最高', 0) or 0),
                float(row.get('最低', 0) or 0),
                float(row.get('收盘', 0) or 0),
                float(row.get('成交量', 0) or 0),
                float(row.get('成交额', 0) or 0),
                float(row.get('振幅', 0) or 0),
                float(row.get('换手率', 0) or 0) if pd.notna(row.get('换手率')) else None,
            ))

        batch.extend(rows)
        if len(batch) >= BATCH_SIZE:
            upsert_kline(batch)
            total_rows += len(batch)
            print(f"  [{i+1}/{len(todo)}] {code}: {len(rows)} rows, batch saved ({total_rows} total, {errors} errors)")
            batch = []
        else:
            print(f"  [{i+1}/{len(todo)}] {code}: {len(rows)} rows")

        time.sleep(API_DELAY)

    if batch:
        upsert_kline(batch)
        total_rows += len(batch)

    print(f"\nDone. Total rows inserted: {total_rows}, errors: {errors}")


if __name__ == '__main__':
    backfill_kline()