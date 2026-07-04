import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from db import upsert_kline, get_all_codes
from ..task_base import BaseTask


class KlineTask(BaseTask):
    task_name = 'kline'
    display_name = '日K线数据'

    def _execute(self):
        today = datetime.now().strftime('%Y-%m-%d')
        codes = get_all_codes()
        total = 0
        errors = 0
        for code in codes:
            if len(code) != 6:
                continue
            try:
                df = ak.fund_etf_hist_em(symbol=code, period='daily',
                                         start_date=today, end_date=today, adjust='')
            except Exception:
                errors += 1
                continue
            if df is None or df.empty:
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
            if rows:
                upsert_kline(rows)
                total += len(rows)
        print(f"[kline] {today}: {total} records, {errors} errors")
        return total