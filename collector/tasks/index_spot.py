import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_index_spot
from ..task_base import BaseTask


class IndexSpotTask(BaseTask):
    task_name = 'index_spot'
    display_name = '指数实时行情'

    def _execute(self):
        df = ak.stock_zh_index_spot_sina()
        now = datetime.now()
        records = []
        for _, row in df.iterrows():
            raw_code = str(row['代码']).strip()
            code = raw_code[2:] if len(raw_code) > 2 and raw_code[:2] in ('sh', 'sz') else raw_code
            name = row['名称']
            price = float(row['最新价']) if pd.notna(row['最新价']) else None
            chg = float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None
            records.append((code, name, price, chg, now))

        if records:
            upsert_index_spot(records)

        print(f"[index_spot] {len(records)} indices updated via Sina")
        return len(records)