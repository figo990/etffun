import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from db import (
    upsert_snapshots, batch_update_fund,
    create_data_source_run, finish_data_source_run, upsert_daily_snapshot_audit,
    infer_trading_date,
)
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
        run_id = create_data_source_run(self.task_name, 'sse_etf_scale')
        try:
            today = datetime.now()
            trading_days = get_recent_trading_days(today, 5)
            sse_df = pd.DataFrame()
            data_date = None
            source_inferred = False
            for d in trading_days:
                try:
                    sse_df = ak.fund_etf_scale_sse(date=d)
                    data_date = d  # API回传的数据日期
                    break
                except Exception:
                    continue
            if sse_df.empty:
                raise RuntimeError("SSE scale data unavailable for recent trading days")
            # Use inferred trading date for the collected date
            inferred_date = infer_trading_date(datetime.now(), exchange='SSE')
            source_inferred = (data_date != to_ymd(inferred_date) if data_date else True)
            store_date = inferred_date.strftime('%Y-%m-%d') if hasattr(inferred_date, 'strftime') else str(inferred_date)[:10]

            snap_rows = []
            fund_rows = []
            audit_rows = []
            for _, row in sse_df.iterrows():
                code = str(row['基金代码'])
                # Skip non-SSE codes (SSE codes start with 5 or 6)
                if not code.startswith(('5', '6')):
                    continue
                total_shares = float(row['基金份额'])
                name = row['基金简称']
                snap_rows.append((code, total_shares, None, None, None, None, None, None, None))
                fund_rows.append((code, name, '沪'))
                audit_rows.append({
                    'date': store_date,
                    'code': code,
                    'source_name': 'sse_etf_scale',
                    'source_url': f'akshare.fund_etf_scale_sse(date={data_date})',
                    'source_date': data_date,
                    'source_date_inferred': source_inferred,
                    'raw_total_shares': total_shares,
                    'raw_unit': '份',
                    'normalized_total_shares': total_shares,
                    'run_id': run_id,
                    'quality_flags': 'SOURCE_DATE_INFERRED' if source_inferred else '',
                })

            if snap_rows:
                upsert_snapshots(store_date, snap_rows)
                batch_update_fund(fund_rows)
                upsert_daily_snapshot_audit(audit_rows)

            count = len(snap_rows)
            finish_data_source_run(run_id, 'success', count)
            print(f"[shares_sse] {store_date}: {count} records (source_date={data_date}, inferred={source_inferred})")
            return count
        except Exception as e:
            finish_data_source_run(run_id, 'failed', 0, str(e))
            raise
