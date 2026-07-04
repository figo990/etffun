import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_sector_fund_flow
from ..task_base import BaseTask


class SectorFundFlowTask(BaseTask):
    task_name = 'sector_fund_flow'
    display_name = '行业资金流向'

    def _execute(self):
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            df = ak.stock_sector_fund_flow_hist(symbol='行业资金流向')
        except Exception as e:
            raise RuntimeError(f"sector fund flow API failed: {e}")

        if df is None or df.empty:
            raise RuntimeError("sector fund flow data empty")

        rows = []
        for _, row in df.iterrows():
            rows.append((
                today,
                str(row.get('名称', '')),
                float(row.get('主力净流入-净额', 0) or 0),
                float(row.get('超大单净流入-净额', 0) or 0),
                float(row.get('大单净流入-净额', 0) or 0),
                float(row.get('中单净流入-净额', 0) or 0),
                float(row.get('小单净流入-净额', 0) or 0),
            ))

        if rows:
            upsert_sector_fund_flow(rows)

        print(f"[sector_fund_flow] {today}: {len(rows)} sectors")
        return len(rows)