import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_etf_option
from ..task_base import BaseTask


OPTION_QVIX_MAP = {
    '510050': ('50ETF', ak.index_option_50etf_qvix),
    '510300': ('300ETF', ak.index_option_300etf_qvix),
    '510500': ('500ETF', ak.index_option_500etf_qvix),
    '588000': ('科创50', ak.index_option_kcb_qvix),
    '159915': ('创业板', ak.index_option_cyb_qvix),
}


class EtfOptionTask(BaseTask):
    task_name = 'etf_option'
    display_name = 'ETF期权数据'

    def _execute(self):
        today_str = datetime.now().strftime('%Y-%m-%d')
        records = []

        for etf_code, (name, qvix_func) in OPTION_QVIX_MAP.items():
            try:
                df = qvix_func()
                if df is None or df.empty:
                    continue

                latest = df.iloc[-1]
                iv_close = float(latest['close']) if pd.notna(latest.get('close')) else None
                iv_high = float(latest['high']) if pd.notna(latest.get('high')) else None
                iv_low = float(latest['low']) if pd.notna(latest.get('low')) else None

                date_val = latest.get('date')
                if date_val is not None:
                    date_str = pd.Timestamp(date_val).strftime('%Y-%m-%d')
                else:
                    date_str = today_str

                records.append((
                    etf_code, date_str, '',
                    f'{name}QVIX',
                    iv_close,
                    iv_high,
                    None,
                    None,
                ))
            except Exception as e:
                print(f"[etf_option] {etf_code} ({name}) error: {e}")
                continue

        if not records:
            try:
                df = ak.option_current_em()
                if df is not None and not df.empty:
                    pass
            except Exception:
                pass

        if records:
            upsert_etf_option(records)

        print(f"[etf_option] {len(records)} option/IV records")
        return len(records)
