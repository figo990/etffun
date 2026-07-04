import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_index_valuation, execute, query
from ..task_base import BaseTask


def _compute_percentile(series, val):
    if val is None or len(series) < 10:
        return None
    below = (series < val).sum()
    return round(below / len(series) * 100, 1)


class IndexValuationTask(BaseTask):
    task_name = 'index_valuation'
    display_name = '指数估值'

    def _execute(self):
        today = datetime.now().strftime('%Y-%m-%d')

        df = query("SELECT DISTINCT index_code, index_name FROM fund WHERE index_code IS NOT NULL")
        all_rows = []
        for _, row in df.iterrows():
            code = row['index_code']
            name = row['index_name']
            try:
                hist = ak.stock_index_hist_pe_em(symbol=name)
            except Exception:
                try:
                    hist = ak.stock_index_hist_pe_em(symbol=code)
                except Exception:
                    continue

            if hist is None or hist.empty:
                continue

            latest = hist.iloc[-1]
            pe = float(latest.get('pe', 0)) if pd.notna(latest.get('pe')) else None
            pb = float(latest.get('pb', 0)) if pd.notna(latest.get('pb')) else None
            dy = float(latest.get('dy', 0)) if pd.notna(latest.get('dy')) else None

            pe_pct = _compute_percentile(hist['pe'].dropna(), pe) if pe else None
            pb_pct = _compute_percentile(hist['pb'].dropna(), pb) if pb else None

            all_rows.append((today, code, name, pe, pb, dy, pe_pct, pb_pct))

        if all_rows:
            upsert_index_valuation(all_rows)

        print(f"[index_valuation] {today}: {len(all_rows)} indices")
        return len(all_rows)