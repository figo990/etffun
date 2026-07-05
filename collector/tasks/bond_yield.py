import akshare as ak
import pandas as pd
from datetime import datetime
from db import execute_many
from ..task_base import BaseTask


class BondYieldTask(BaseTask):
    task_name = 'bond_yield'
    display_name = '国债收益率'

    def _execute(self):
        try:
            df = ak.bond_zh_us_rate()
        except Exception as e:
            raise RuntimeError(f"bond yield API failed: {e}")

        if df is None or df.empty:
            raise RuntimeError("bond yield data empty")

        rows = []
        for _, r in df.iterrows():
            d = r['日期']
            if isinstance(d, pd.Timestamp):
                d = d.strftime('%Y-%m-%d')
            else:
                d = str(d)[:10]
            rows.append((
                d,
                None,
                float(r['中国国债收益率2年']) if pd.notna(r.get('中国国债收益率2年')) else None,
                float(r['中国国债收益率5年']) if pd.notna(r.get('中国国债收益率5年')) else None,
                float(r['中国国债收益率10年']) if pd.notna(r.get('中国国债收益率10年')) else None,
                float(r['中国国债收益率30年']) if pd.notna(r.get('中国国债收益率30年')) else None,
                float(r['中国国债收益率10年-2年']) if pd.notna(r.get('中国国债收益率10年-2年')) else None,
            ))

        if rows:
            sql = """INSERT INTO bond_yield (date, y1, y2, y5, y10, y30, spread_10_2)
                     VALUES (?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (date) DO UPDATE SET
                         y1=COALESCE(EXCLUDED.y1,bond_yield.y1),
                         y2=COALESCE(EXCLUDED.y2,bond_yield.y2),
                         y5=COALESCE(EXCLUDED.y5,bond_yield.y5),
                         y10=COALESCE(EXCLUDED.y10,bond_yield.y10),
                         y30=COALESCE(EXCLUDED.y30,bond_yield.y30),
                         spread_10_2=COALESCE(EXCLUDED.spread_10_2,bond_yield.spread_10_2)"""
            execute_many(sql, rows)

        print(f"[bond_yield] {len(rows)} records, {rows[-1][0]} ~ {rows[0][0]}")
        return len(rows)