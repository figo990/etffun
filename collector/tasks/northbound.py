import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_northbound_flow
from ..task_base import BaseTask


class NorthboundTask(BaseTask):
    task_name = 'northbound'
    display_name = '北向资金流'

    def _execute(self):
        merged = {}

        # Source 1: EM total (historically 60 days up to 2024-08-16)
        try:
            df = ak.stock_hsgt_hist_em(symbol='北向资金')
            if df is not None and not df.empty:
                for _, row in df[df['当日成交净买额'].notna()].iterrows():
                    d = pd.Timestamp(row['日期']).strftime('%Y-%m-%d')
                    merged[d] = (None, None, float(row['当日成交净买额']))
        except Exception as e:
            print(f"[northbound] 北向合计获取失败: {e}")

        # Source 2: EM individual channels (more granular if total fails)
        try:
            for sym, key in [('沪股通', 0), ('深股通', 1)]:
                df = ak.stock_hsgt_hist_em(symbol=sym)
                if df is not None and not df.empty:
                    for _, row in df[df['当日成交净买额'].notna()].iterrows():
                        d = pd.Timestamp(row['日期']).strftime('%Y-%m-%d')
                        cur = list(merged.get(d, (None, None, None)))
                        cur[key] = float(row['当日成交净买额'])
                        merged[d] = tuple(cur)
        except Exception as e:
            print(f"[northbound] 分渠道获取失败: {e}")

        # Source 3: summary API (latest trading day, always runs)
        try:
            df = ak.stock_hsgt_fund_flow_summary_em()
            if df is not None and not df.empty:
                north = df[df['资金方向'] == '北向']
                for d in north['交易日'].unique():
                    day = north[north['交易日'] == d]
                    sh = float(day[day['板块'] == '沪股通']['成交净买额'].iloc[0]) if not day[day['板块'] == '沪股通'].empty else 0
                    sz = float(day[day['板块'] == '深股通']['成交净买额'].iloc[0]) if not day[day['板块'] == '深股通'].empty else 0
                    merged[pd.Timestamp(d).strftime('%Y-%m-%d')] = (sh, sz, sh + sz)
        except Exception as e:
            print(f"[northbound] 摘要获取失败: {e}")

        records = []
        for d in sorted(merged.keys())[-60:]:
            sh, sz, total = merged[d]
            records.append((d, sh, sz, total, None, None, None, None))

        if records:
            upsert_northbound_flow(records)

        print(f"[northbound] {len(records)} days of flow data")
        return len(records)
