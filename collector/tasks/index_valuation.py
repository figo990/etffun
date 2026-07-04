import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_index_valuation, query
from ..task_base import BaseTask


def _compute_percentile(series, val):
    if val is None or len(series) < 10:
        return None
    below = (series < val).sum()
    return round(below / len(series) * 100, 1)


def _fetch_pe_history(name, code):
    sources = [
        ('pe_lg_name', lambda: ak.stock_index_pe_lg(symbol=name)),
        ('hist_csindex_code', lambda: ak.stock_zh_index_hist_csindex(symbol=code)),
    ]
    for label, fetcher in sources:
        try:
            df = fetcher()
            if df is not None and not df.empty:
                pe_cols = [c for c in df.columns if '静态市盈率' in c]
                pb_cols = [c for c in df.columns if '市净率' in c]
                has_pe = any('市盈率' in c for c in df.columns) or len(pe_cols) > 0
                if has_pe:
                    return df, label
        except Exception:
            continue
    return None, None


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

            hist, source = _fetch_pe_history(name, code)
            if hist is None:
                try:
                    val_df = ak.stock_zh_index_value_csindex(symbol=code)
                    if val_df is not None and not val_df.empty:
                        latest = val_df.iloc[-1]
                        pe = float(latest.get('市盈率1', 0)) if pd.notna(latest.get('市盈率1')) else None
                        pe2 = float(latest.get('市盈率2', 0)) if pd.notna(latest.get('市盈率2')) else None
                        dy1 = float(latest.get('股息率1', 0)) if pd.notna(latest.get('股息率1')) else None
                        all_rows.append((today, code, name, pe or pe2, None, dy1, None, None))
                    continue
                except Exception:
                    continue

            if source == 'pe_lg_name':
                latest = hist.iloc[-1]
                pe = float(latest.get('静态市盈率', 0)) if pd.notna(latest.get('静态市盈率')) else None
                pe_ttm = float(latest.get('滚动市盈率', 0)) if pd.notna(latest.get('滚动市盈率')) else None
                pe_pct = _compute_percentile(hist['静态市盈率'].dropna(), pe) if pe else None
                pb_pct = _compute_percentile(hist['滚动市盈率'].dropna(), pe_ttm) if pe_ttm else None
                all_rows.append((today, code, name, pe, None, None, pe_pct, pb_pct))
            elif source == 'hist_csindex_code':
                latest = hist.iloc[-1]
                pe = float(latest.get('滚动市盈率', 0)) if pd.notna(latest.get('滚动市盈率')) else None
                pe_pct = _compute_percentile(hist['滚动市盈率'].dropna(), pe) if pe is not None else None
                try:
                    val_df = ak.stock_zh_index_value_csindex(symbol=code)
                    if val_df is not None and not val_df.empty:
                        v = val_df.iloc[-1]
                        pe2 = float(v.get('市盈率1', 0)) if pd.notna(v.get('市盈率1')) else None
                        pb = float(v.get('市盈率2', 0)) if pd.notna(v.get('市盈率2')) else None
                        dy1 = float(v.get('股息率1', 0)) if pd.notna(v.get('股息率1')) else None
                        all_rows.append((today, code, name, pe2 or pe, pb, dy1, pe_pct, None))
                        continue
                except Exception:
                    pass
                all_rows.append((today, code, name, pe, None, None, pe_pct, None))

        if all_rows:
            upsert_index_valuation(all_rows)

        print(f"[index_valuation] {today}: {len(all_rows)} indices")
        return len(all_rows)
