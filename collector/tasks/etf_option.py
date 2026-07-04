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


class _TimeoutError(Exception):
    pass


def _fetch_pcr_data():
    """Fetch PCR data with 20s timeout (EM API may hang)."""
    import signal
    def _handler(signum, frame):
        raise _TimeoutError("PCR fetch timed out")
    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(20)
    try:
        df = ak.option_current_em()
        signal.alarm(0)
        if df is None or df.empty:
            return {}
        pcr_data = {}
        for _, row in df.iterrows():
            code = str(row.get('期权代码', '')).strip()
            name = str(row.get('期权名称', ''))
            pcr_v = float(row['持仓量/成交量比']) if pd.notna(row.get('持仓量/成交量比')) else None
            pcr_oi = float(row['成交量/持仓量比']) if pd.notna(row.get('成交量/持仓量比')) else None
            for etf_code, (_, _) in OPTION_QVIX_MAP.items():
                if etf_code in code or etf_code in name:
                    if etf_code not in pcr_data:
                        pcr_data[etf_code] = {'pcr_volume': None, 'pcr_oi': None}
                    if pcr_v is not None:
                        pcr_data[etf_code]['pcr_volume'] = pcr_v
                    if pcr_oi is not None:
                        pcr_data[etf_code]['pcr_oi'] = pcr_oi
                    break
        return pcr_data
    except _TimeoutError:
        print("  [etf_option] PCR fetch timed out")
        return {}
    except Exception as e:
        print(f"  [etf_option] PCR fetch error: {e}")
        return {}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


class EtfOptionTask(BaseTask):
    task_name = 'etf_option'
    display_name = 'ETF期权数据'

    def _execute(self):
        today_str = datetime.now().strftime('%Y-%m-%d')
        records = []

        pcr_data = _fetch_pcr_data()

        for etf_code, (name, qvix_func) in OPTION_QVIX_MAP.items():
            try:
                df = qvix_func()
                if df is None or df.empty:
                    continue

                latest = df.iloc[-1]
                qvix_close = float(latest['close']) if pd.notna(latest.get('close')) else None
                qvix_high = float(latest['high']) if pd.notna(latest.get('high')) else None

                date_val = latest.get('date')
                if date_val is not None:
                    date_str = pd.Timestamp(date_val).strftime('%Y-%m-%d')
                else:
                    date_str = today_str

                pcr = pcr_data.get(etf_code, {})
                call_iv = qvix_close
                put_iv = qvix_high if qvix_high else qvix_close

                records.append((
                    etf_code, date_str, '',
                    f'{name}QVIX',
                    call_iv,
                    put_iv,
                    pcr.get('pcr_volume'),
                    pcr.get('pcr_oi'),
                ))
            except Exception as e:
                print(f"[etf_option] {etf_code} ({name}) error: {e}")
                continue

        if records:
            upsert_etf_option(records)

        print(f"[etf_option] {len(records)} option/IV records for {today_str}")
        return len(records)
