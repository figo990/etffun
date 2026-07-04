import akshare as ak
import pandas as pd
import concurrent.futures
from datetime import datetime, timedelta
from db import upsert_kline, get_all_codes, query
from ..task_base import BaseTask


def _fetch_single(code, start_short, end_short, timeout=20):
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(ak.fund_etf_hist_em, symbol=code, period='daily',
                               start_date=start_short, end_date=end_short, adjust='')
            df = future.result(timeout=timeout)
            if df is None or df.empty:
                return code, None
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
            return code, rows
    except concurrent.futures.TimeoutError:
        return code, []
    except Exception:
        return code, []


class KlineTask(BaseTask):
    task_name = 'kline'
    display_name = '日K线数据'

    def _execute(self):
        today = datetime.now().strftime('%Y-%m-%d')

        max_date = query("SELECT MAX(date) AS md FROM daily_kline")
        md = max_date.iloc[0]['md'] if max_date is not None and not max_date.empty else None

        if md is None or pd.isna(md):
            start_date = '2025-01-01'
        else:
            if hasattr(md, 'strftime'):
                md_str = md.strftime('%Y-%m-%d')
            else:
                md_str = str(md)[:10]
            start = datetime.strptime(md_str, '%Y-%m-%d') - timedelta(days=1)
            start_date = start.strftime('%Y-%m-%d')

        start_short = start_date.replace('-', '')
        today_short = today.replace('-', '')

        codes = get_all_codes()
        total = 0
        errors = 0
        for i, code in enumerate(codes):
            if len(code) != 6:
                continue
            _, rows = _fetch_single(code, start_short, today_short)
            if rows:
                upsert_kline(rows)
                total += len(rows)
            else:
                errors += 1
            if (i + 1) % 200 == 0:
                print(f"[kline] {i+1}/{len(codes)} codes, {total} records so far", flush=True)
        print(f"[kline] {start_date}~{today}: {total} records, {errors} errors", flush=True)
        return total
