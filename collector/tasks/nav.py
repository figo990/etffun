import akshare as ak
import pandas as pd
from datetime import datetime
from db import execute_many
from ..task_base import BaseTask


class NavTask(BaseTask):
    task_name = 'nav'
    display_name = '净值数据'

    def _execute(self):
        today_str = datetime.now().strftime('%Y%m%d')
        df = ak.fund_etf_spot_ths(date=today_str)
        today_ymd = datetime.now().strftime('%Y-%m-%d')

        updates = []
        for _, row in df.iterrows():
            code = str(row['基金代码'])
            nav = float(row['当前-单位净值']) if pd.notna(row['当前-单位净值']) else None
            nav_date = str(row['最新-交易日']) if pd.notna(row['最新-交易日']) else None
            if nav is not None and nav_date:
                updates.append((nav, nav_date, code, today_ymd))

        if updates:
            execute_many(
                "UPDATE daily_snapshot SET nav = ?, nav_date = ? WHERE code = ? AND date = ?",
                updates
            )

        print(f"[nav] {len(updates)} NAV records updated for {today_ymd}")
        return len(updates)