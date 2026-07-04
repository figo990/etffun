import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from db import upsert_snapshots, batch_update_fund
from ..task_base import BaseTask, retry


def to_ymd(dt):
    return dt.strftime('%Y%m%d')


def get_recent_trading_days(base, n=5):
    days = []
    d = base
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return [to_ymd(d) for d in days]


class SharesSSETask(BaseTask):
    task_name = 'shares_sse'
    display_name = '上交所ETF份额'

    def _execute(self):
        today = datetime.now()
        trading_days = get_recent_trading_days(today, 5)
        sse_df = pd.DataFrame()
        data_date = None
        for d in trading_days:
            try:
                sse_df = ak.fund_etf_scale_sse(date=d)
                data_date = d
                break
            except Exception:
                continue
        if sse_df.empty:
            raise RuntimeError("SSE scale data unavailable for recent trading days")

        snap_rows = []
        fund_rows = []
        for _, row in sse_df.iterrows():
            code = str(row['基金代码'])
            total_shares = float(row['基金份额'])
            name = row['基金简称']
            snap_rows.append((code, total_shares, None, None, None, None, None, None, None))
            fund_rows.append((code, name, '沪'))

        if snap_rows:
            upsert_snapshots(data_date, snap_rows)
            batch_update_fund(fund_rows)

        count = len(snap_rows)
        print(f"[shares_sse] {data_date}: {count} records")
        return count
