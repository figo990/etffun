import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_bond_yield, upsert_margin_detail, get_all_codes
from ..task_base import BaseTask


class BondYieldTask(BaseTask):
    task_name = 'bond_yield'
    display_name = '国债收益率'

    def _execute(self):
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            df = ak.bond_china_yield()
        except Exception as e:
            raise RuntimeError(f"bond yield API failed: {e}")

        if df is None or df.empty:
            raise RuntimeError("bond yield data empty")

        row = df.iloc[-1]
        upsert_bond_yield(
            date_str=today,
            y1=float(row.get('1年', 0) or 0) if pd.notna(row.get('1年')) else None,
            y2=float(row.get('2年', 0) or 0) if pd.notna(row.get('2年')) else None,
            y5=float(row.get('5年', 0) or 0) if pd.notna(row.get('5年')) else None,
            y10=float(row.get('10年', 0) or 0) if pd.notna(row.get('10年')) else None,
            y30=float(row.get('30年', 0) or 0) if pd.notna(row.get('30年')) else None,
            spread=None,
        )
        print(f"[bond_yield] {today}: inserted")
        return 1


class MarginDetailTask(BaseTask):
    task_name = 'margin_detail'
    display_name = '融资融券'

    def _execute(self):
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            df = ak.stock_margin_detail_em(date=today)
        except Exception as e:
            raise RuntimeError(f"margin detail API failed: {e}")

        if df is None or df.empty:
            raise RuntimeError("margin detail data empty")

        etf_codes = set(get_all_codes())
        rows = []
        for _, row in df.iterrows():
            code = str(row.get('代码', ''))
            if code not in etf_codes:
                continue
            rows.append((
                today, code,
                float(row.get('融资余额', 0) or 0),
                float(row.get('融资买入额', 0) or 0),
                float(row.get('融资偿还额', 0) or 0),
                float(row.get('融资净买入', 0) or 0),
                float(row.get('融券余额', 0) or 0),
            ))

        if rows:
            upsert_margin_detail(rows)

        print(f"[margin_detail] {today}: {len(rows)} records")
        return len(rows)