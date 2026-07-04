import akshare as ak
import pandas as pd
import concurrent.futures
from datetime import datetime, timedelta
from db import upsert_kline, get_all_codes, query
from ..task_base import BaseTask


def _code_to_prefix(code):
    return 'sh' if code[0] in ('5', '6') else 'sz'


def _fetch_single_sina(code, start_date_str, end_date_str, timeout=20):
    prefix = _code_to_prefix(code)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(ak.fund_etf_hist_sina, symbol=prefix + code)
            df = future.result(timeout=timeout)
            if df is None or df.empty:
                return code, None
            df = df.sort_values('date')
            df['date'] = pd.to_datetime(df['date'])
            start_dt = pd.Timestamp(start_date_str)
            end_dt = pd.Timestamp(end_date_str)
            df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
            if df.empty:
                return code, []
            df['prev_close'] = df['close'].shift(1)
            rows = []
            for _, row in df.iterrows():
                d = row['date'].strftime('%Y-%m-%d')
                amp = None
                pc = row.get('prev_close')
                if pc is not None and pc > 0:
                    amp = round((float(row['high']) - float(row['low'])) / pc * 100, 2)
                rows.append((
                    d, code,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    int(row['amount']),
                    amp,
                    None,
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

        codes = get_all_codes()
        total = 0
        errors = 0
        for i, code in enumerate(codes):
            if len(code) != 6:
                continue
            _, rows = _fetch_single_sina(code, start_date, today)
            if rows:
                upsert_kline(rows)
                total += len(rows)
            else:
                errors += 1
            if (i + 1) % 200 == 0:
                print(f"[kline] {i+1}/{len(codes)} codes, {total} records so far", flush=True)
        print(f"[kline] {start_date}~{today}: {total} records, {errors} errors", flush=True)
        return total
