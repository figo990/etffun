import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from db import upsert_margin_detail, get_all_codes
from ..task_base import BaseTask


def _fetch_sse(date_str):
    try:
        df = ak.stock_margin_detail_sse(date=date_str)
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    result = {}
    for _, row in df.iterrows():
        code = str(row.get('标的证券代码', '')).strip()
        balance = float(row.get('融资余额', 0) or 0)
        buy = float(row.get('融资买入额', 0) or 0)
        sell = float(row.get('融资偿还额', 0) or 0)
        result[code] = [balance, buy, sell, buy - sell, 0.0]
    return result


def _fetch_szse(date_str):
    try:
        df = ak.stock_margin_detail_szse(date=date_str)
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    result = {}
    for _, row in df.iterrows():
        code = str(row.get('证券代码', '')).strip()
        balance = float(row.get('融资余额', 0) or 0)
        buy = float(row.get('融资买入额', 0) or 0)
        short_b = float(row.get('融券余额', 0) or 0)
        result[code] = [balance, buy, 0.0, 0.0, short_b]
    return result


def _merge_margin(sse_data, szse_data, etf_codes):
    combined = {}
    for code, vals in sse_data.items():
        if code in etf_codes:
            combined[code] = vals
    for code, vals in szse_data.items():
        if code in etf_codes:
            if code in combined:
                existing = combined[code]
                existing[2] = vals[2]
                existing[4] = vals[4]
            else:
                combined[code] = vals
    return combined


class MarginDetailTask(BaseTask):
    task_name = 'margin_detail'
    display_name = '融资融券'

    def _execute(self):
        today = datetime.now()
        today_str = today.strftime('%Y%m%d')
        today_date = today.strftime('%Y-%m-%d')
        etf_codes = set(get_all_codes())

        # Check if backfill needed
        from db import query as db_query
        max_row = db_query("SELECT MAX(date) AS md FROM margin_detail")
        max_date = max_row.iloc[0]['md'] if max_row is not None and not max_row.empty else None

        if max_date is None:
            dates = pd.bdate_range(
                end=today.date() - timedelta(days=1),
                periods=60
            )
            total = 0
            for d in dates:
                ds = d.strftime('%Y%m%d')
                try:
                    sse = _fetch_sse(ds)
                    szse = _fetch_szse(ds)
                except Exception:
                    continue
                if not sse and not szse:
                    continue
                combined = _merge_margin(sse, szse, etf_codes)
                rows = [(ds[:4] + '-' + ds[4:6] + '-' + ds[6:], c, v[0], v[1], v[2], v[3], v[4])
                        for c, v in combined.items()]
                if rows:
                    upsert_margin_detail(rows)
                    total += len(rows)
            print(f"[margin_detail] backfill: {total} records from {dates[0].strftime('%Y-%m-%d')}")

        sse_data = _fetch_sse(today_str)
        szse_data = _fetch_szse(today_str)

        if not sse_data and not szse_data:
            print(f"[margin_detail] {today_date}: no data (weekend/holiday)")
            return 0

        combined = _merge_margin(sse_data, szse_data, etf_codes)

        rows = [(today_date, code, vals[0], vals[1], vals[2], vals[3], vals[4])
                for code, vals in combined.items()]

        if rows:
            upsert_margin_detail(rows)

        print(f"[margin_detail] {today_date}: {len(rows)} records")
        return len(rows)
