from datetime import datetime

import akshare as ak
import pandas as pd

from db import (
    bootstrap_huijin_support_data,
    create_data_source_run,
    DB_PATH,
    finish_data_source_run,
    infer_trading_date,
    READ_DB_PATH,
    sync_tables,
    upsert_cffex_position_rank,
)
from ..task_base import BaseTask


class CffexPositionRankTask(BaseTask):
    task_name = 'cffex_position_rank'
    display_name = '中金所持仓排名'

    def _execute(self):
        run_id = create_data_source_run(self.task_name, 'cffex_position_rank')
        try:
            bootstrap_huijin_support_data(refresh_issues=False)
            trading_date = infer_trading_date(datetime.now(), exchange='CFFEX')
            raw = ak.get_cffex_rank_table(
                date=trading_date.replace('-', ''),
                vars_list=['IF', 'IH', 'IC', 'IM'],
            )
            df = _normalize_rank_payload(raw, trading_date)
            if df is None or df.empty:
                raise RuntimeError(f"CFFEX rank data unavailable for {trading_date}")

            rows = []
            for _, r in df.iterrows():
                contract = str(r.get('symbol') or '').strip()
                if not contract:
                    continue
                rank_no = _to_int(r.get('rank'))
                if rank_no == 999:
                    continue
                source_date = _norm_date(r.get('date')) or trading_date
                for rank_type, name_col, volume_col, change_col in [
                    ('volume', 'vol_party_name', 'vol', 'vol_chg'),
                    ('long', 'long_party_name', 'long_open_interest', 'long_open_interest_chg'),
                    ('short', 'short_party_name', 'short_open_interest', 'short_open_interest_chg'),
                ]:
                    member_name = _clean(r.get(name_col))
                    if not member_name:
                        continue
                    rows.append({
                        'date': source_date,
                        'contract': contract,
                        'rank_type': rank_type,
                        'rank_no': rank_no,
                        'member_name': member_name,
                        'volume': _to_float(r.get(volume_col)),
                        'change': _to_float(r.get(change_col)),
                        'source_name': 'akshare.get_cffex_rank_table',
                        'run_id': run_id,
                    })

            upsert_cffex_position_rank(rows)
            finish_data_source_run(run_id, 'success', len(rows))
            synced = 0
            if DB_PATH != READ_DB_PATH:
                synced = sync_tables(['cffex_position_rank', 'data_source_run'])
            print(f"[cffex_position_rank] {trading_date}: {len(rows)} rows synced_tables={synced}")
            return len(rows)
        except Exception as e:
            finish_data_source_run(run_id, 'failed', 0, str(e))
            raise


def _clean(value):
    if value is None or pd.isna(value):
        return ''
    return str(value).strip()


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    number = _to_float(value)
    return int(number) if number is not None else None


def _norm_date(value):
    if value is None or pd.isna(value):
        return None
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    s = str(value).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


def _normalize_rank_payload(raw, trading_date):
    if raw is None:
        return pd.DataFrame()
    if isinstance(raw, pd.DataFrame):
        return raw
    if isinstance(raw, dict):
        frames = []
        for contract, frame in raw.items():
            if frame is None or getattr(frame, 'empty', True):
                continue
            f = frame.copy()
            if 'symbol' not in f.columns:
                f['symbol'] = contract
            if 'date' not in f.columns:
                f['date'] = trading_date
            frames.append(f)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return pd.DataFrame()
