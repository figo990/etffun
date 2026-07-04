import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_margin_detail, get_all_codes
from ..task_base import BaseTask


def _fetch_sse(today_str):
    """Fetch SSE margin detail (date in YYYYMMDD format)."""
    df = ak.stock_margin_detail_sse(date=today_str)
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


def _fetch_szse(today_str):
    """Fetch SZSE margin detail (date in YYYYMMDD format)."""
    df = ak.stock_margin_detail_szse(date=today_str)
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


class MarginDetailTask(BaseTask):
    task_name = 'margin_detail'
    display_name = '融资融券'

    def _execute(self):
        today_str = datetime.now().strftime('%Y%m%d')
        today_date = datetime.now().strftime('%Y-%m-%d')

        sse_data = _fetch_sse(today_str)
        szse_data = _fetch_szse(today_str)

        if not sse_data and not szse_data:
            raise RuntimeError("margin detail data unavailable")

        etf_codes = set(get_all_codes())
        combined = {}
        for code, vals in sse_data.items():
            if code in etf_codes:
                combined[code] = vals
        for code, vals in szse_data.items():
            if code in etf_codes:
                if code in combined:
                    existing = combined[code]
                    existing[2] = vals[2]   # margin_sell
                    existing[4] = vals[4]   # short_balance
                else:
                    combined[code] = vals

        rows = []
        for code, vals in combined.items():
            rows.append((today_date, code, vals[0], vals[1], vals[2], vals[3], vals[4]))

        if rows:
            upsert_margin_detail(rows)

        print(f"[margin_detail] {today_date}: {len(rows)} records")
        return len(rows)