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
        rows = []

        # Primary: EM historical API
        try:
            df = ak.stock_sector_fund_flow_hist(symbol='行业资金流向')
            if df is not None and not df.empty:
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
        except Exception as e:
            print(f"[sector_fund_flow] EM API failed: {e}")

        # Fallback: 同花顺 industry flow (current day only, non-EM)
        if not rows:
            try:
                df = ak.stock_fund_flow_industry(symbol='即时')
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        rows.append((
                            today,
                            str(row.get('行业', '')),
                            float(row.get('净额', 0) or 0),
                            None,
                            None,
                            None,
                            None,
                        ))
            except Exception as e:
                print(f"[sector_fund_flow] THS fallback failed: {e}")

        if not rows:
            raise RuntimeError("sector fund flow data empty (both primary and fallback failed)")

        upsert_sector_fund_flow(rows)
        print(f"[sector_fund_flow] {today}: {len(rows)} sectors")
        return len(rows)