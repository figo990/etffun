import akshare as ak
from datetime import datetime
from db import upsert_margin_detail, get_all_codes
from ..task_base import BaseTask


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