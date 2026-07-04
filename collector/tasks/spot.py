import akshare as ak
import pandas as pd
from datetime import datetime
from db import execute_many
from ..task_base import BaseTask


class SpotTask(BaseTask):
    task_name = 'spot'
    display_name = '实时行情'

    def _execute(self):
        df = ak.fund_etf_spot_em()
        today_str = datetime.now().strftime('%Y-%m-%d')

        rows = []
        for _, row in df.iterrows():
            code = str(row['代码'])
            price = float(row['最新价']) if pd.notna(row['最新价']) else None
            chg = float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None
            turnover = float(row['成交额']) if pd.notna(row['成交额']) else None
            iopv = float(row['IOPV实时估值']) if pd.notna(row.get('IOPV实时估值')) else None
            disc = float(row['基金折价率']) if pd.notna(row.get('基金折价率')) else None
            rows.append((today_str, code, price, chg, turnover, iopv, disc,
                         price, chg, turnover, iopv, disc))

        if rows:
            execute_many("""
                INSERT INTO daily_snapshot
                    (date, code, total_shares, price, price_change_pct, turnover, iopv, discount_rt)
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
                ON CONFLICT (date, code) DO UPDATE SET
                    price        = COALESCE(?, daily_snapshot.price),
                    price_change_pct = COALESCE(?, daily_snapshot.price_change_pct),
                    turnover     = COALESCE(?, daily_snapshot.turnover),
                    iopv         = COALESCE(?, daily_snapshot.iopv),
                    discount_rt  = COALESCE(?, daily_snapshot.discount_rt)
            """, rows)

        spot_count = len(df)
        print(f"[spot] {spot_count} spots batch-upserted for {today_str}")
        return spot_count