"""SSE ETF share data collector - uses SSE official API directly"""
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
from db import (
    upsert_snapshots, batch_update_fund,
    create_data_source_run, finish_data_source_run, upsert_daily_snapshot_audit,
    infer_trading_date,
)
from ..task_base import BaseTask


def _make_session():
    sess = requests.Session()
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=1, pool_maxsize=1)
    sess.mount('https://', adapter)
    sess.mount('http://', adapter)
    return sess


def _to_ymd(dt):
    return dt.strftime('%Y%m%d')


def _fetch_sse_data(date_str, retries=3):
    """Fetch SSE ETF share data via official API."""
    data_str = "-".join([date_str[:4], date_str[4:6], date_str[6:]])
    url = "https://query.sse.com.cn/commonQuery.do"
    params = {
        "isPagination": "true",
        "pageHelp.pageSize": "10000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
        "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
        "STAT_DATE": data_str,
    }
    headers = {
        "Referer": "https://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    sess = _make_session()
    for attempt in range(retries):
        try:
            r = sess.get(url, params=params, headers=headers, timeout=60)
            r.raise_for_status()
            data_json = r.json()
            result = data_json.get("result", [])
            if result:
                return result, date_str
        except Exception as e:
            if attempt < retries - 1:
                import time
                time.sleep(5 * (attempt + 1))
    return None, None


def get_recent_trading_days(base, n=5):
    days = []
    d = base
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return [_to_ymd(d) for d in days]


class SharesSSETask(BaseTask):
    task_name = 'shares_sse'
    display_name = '上交所ETF份额'

    def _execute(self):
        run_id = create_data_source_run(self.task_name, 'sse_etf_scale')
        try:
            # Determine the correct trading date
            inferred_date = infer_trading_date(datetime.now(), exchange='SSE')
            target_str = _to_ymd(inferred_date) if hasattr(inferred_date, 'strftime') else str(inferred_date)[:10].replace('-', '')
            trading_days = get_recent_trading_days(
                datetime.strptime(target_str, '%Y%m%d') if len(target_str) == 8 else datetime.now(), 5)

            result = None
            data_date = None
            for d in trading_days:
                result, data_date = _fetch_sse_data(d)
                if result:
                    break

            if not result:
                raise RuntimeError("SSE scale data unavailable for recent trading days")

            snap_rows = []
            fund_rows = []
            audit_rows = []
            for item in result:
                code = str(item.get('SEC_CODE', ''))
                if not code.startswith(('5', '6')):
                    continue
                total_shares = float(item.get('TOT_VOL', 0)) * 10000
                name = item.get('SEC_NAME', '')
                api_date = str(item.get('STAT_DATE', data_date))[:10]
                snap_rows.append((code, total_shares, None, None, None, None, None, None, None))
                fund_rows.append((code, name, '沪'))
                audit_rows.append({
                    'date': api_date,
                    'code': code,
                    'source_name': 'sse_etf_scale',
                    'source_url': f'sse.api.commonQuery(STAT_DATE={data_date})',
                    'source_date': api_date,
                    'source_date_inferred': False,
                    'raw_total_shares': total_shares,
                    'raw_unit': '份',
                    'normalized_total_shares': total_shares,
                    'run_id': run_id,
                    'quality_flags': '',
                })

            if snap_rows:
                upsert_snapshots(api_date, snap_rows)
                batch_update_fund(fund_rows)
                upsert_daily_snapshot_audit(audit_rows)

            count = len(snap_rows)
            finish_data_source_run(run_id, 'success', count)
            print(f"[shares_sse] {api_date}: {count} records")
            return count
        except Exception as e:
            finish_data_source_run(run_id, 'failed', 0, str(e))
            raise