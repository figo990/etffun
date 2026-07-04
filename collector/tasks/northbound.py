import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_northbound_flow
from ..task_base import BaseTask


class NorthboundTask(BaseTask):
    task_name = 'northbound'
    display_name = '北向资金流'

    def _execute(self):
        records = []

        # Primary: EM historical API
        try:
            df = ak.stock_hsgt_hist_em(symbol='北向资金')
            if df is not None and not df.empty:
                valid = df[df['当日成交净买额'].notna()]
                for _, row in valid.tail(60).iterrows():
                    date_val = row.get('日期')
                    if date_val is None:
                        continue
                    date_str = pd.Timestamp(date_val).strftime('%Y-%m-%d')
                    total_net = float(row['当日成交净买额']) if pd.notna(row.get('当日成交净买额')) else None
                    records.append((date_str, None, None, total_net, None, None, None, None))
        except Exception as e:
            print(f"[northbound] 北向合计获取失败: {e}")

        if not records:
            try:
                sh_df = ak.stock_hsgt_hist_em(symbol='沪股通')
                sz_df = ak.stock_hsgt_hist_em(symbol='深股通')

                sh_dict = {}
                if sh_df is not None and not sh_df.empty:
                    valid_sh = sh_df[sh_df['当日成交净买额'].notna()]
                    for _, row in valid_sh.tail(60).iterrows():
                        d = pd.Timestamp(row['日期']).strftime('%Y-%m-%d')
                        sh_dict[d] = float(row['当日成交净买额'])

                sz_dict = {}
                if sz_df is not None and not sz_df.empty:
                    valid_sz = sz_df[sz_df['当日成交净买额'].notna()]
                    for _, row in valid_sz.tail(60).iterrows():
                        d = pd.Timestamp(row['日期']).strftime('%Y-%m-%d')
                        sz_dict[d] = float(row['当日成交净买额'])

                all_dates = sorted(set(list(sh_dict.keys()) + list(sz_dict.keys())))
                for d in all_dates[-60:]:
                    sh = sh_dict.get(d, 0)
                    sz = sz_dict.get(d, 0)
                    records.append((d, sh, sz, sh + sz, None, None, None, None))
            except Exception as e:
                print(f"[northbound] 分渠道获取失败: {e}")

        # Fallback: summary API (current day only, non-EM)
        if not records:
            try:
                df = ak.stock_hsgt_fund_flow_summary_em()
                if df is not None and not df.empty:
                    north = df[df['资金方向'] == '北向']
                    dates = north['交易日'].unique()
                    for d in dates:
                        day_rows = north[north['交易日'] == d]
                        date_str = pd.Timestamp(d).strftime('%Y-%m-%d')
                        sh_val = float(day_rows[day_rows['板块'] == '沪股通']['成交净买额'].iloc[0]) if not day_rows[day_rows['板块'] == '沪股通'].empty else 0
                        sz_val = float(day_rows[day_rows['板块'] == '深股通']['成交净买额'].iloc[0]) if not day_rows[day_rows['板块'] == '深股通'].empty else 0
                        records.append((date_str, sh_val, sz_val, sh_val + sz_val, None, None, None, None))
            except Exception as e:
                print(f"[northbound] 摘要获取失败: {e}")

        if records:
            upsert_northbound_flow(records)

        print(f"[northbound] {len(records)} days of flow data")
        return len(records)
