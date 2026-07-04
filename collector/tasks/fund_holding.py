import akshare as ak
import pandas as pd
import re
from datetime import datetime
from db import upsert_fund_holdings
from ..task_base import BaseTask


def parse_quarter_date(quarter_str):
    """Parse '2026年1季度股票投资明细' -> '2026-03-31'"""
    m = re.match(r'(\d{4})年(\d)季度', str(quarter_str))
    if not m:
        return None
    year, q = int(m.group(1)), int(m.group(2))
    quarter_end = {1: f'{year}-03-31', 2: f'{year}-06-30',
                   3: f'{year}-09-30', 4: f'{year}-12-31'}
    return quarter_end.get(q)


class HoldingTask(BaseTask):
    task_name = 'fund_holding'
    display_name = 'ETF持仓数据'

    TARGET_CODES = [
        '510050', '510300', '510500', '159919', '159915',
        '512100', '512010', '512880', '515790', '159995',
        '518880', '513050', '513100', '513180', '159941',
        '512690', '512660', '512800', '159869', '562010',
    ]

    def _execute(self):
        total = 0
        for code in self.TARGET_CODES:
            try:
                df = ak.fund_portfolio_hold_em(symbol=code, date='')
                if df is None or df.empty:
                    continue

                quarter_str = df['季度'].iloc[0] if '季度' in df.columns else None
                report_date = parse_quarter_date(quarter_str) if quarter_str else None
                if report_date is None:
                    continue

                holdings = []
                for _, row in df.head(10).iterrows():
                    holdings.append({
                        'stock_code': str(row.get('股票代码', '')),
                        'stock_name': str(row.get('股票名称', '')),
                        'hold_pct': float(row['占净值比例']) if pd.notna(row.get('占净值比例')) else None,
                        'hold_amount': float(row['持股数']) if pd.notna(row.get('持股数')) else None,
                        'hold_value': float(row['持仓市值']) if pd.notna(row.get('持仓市值')) else None,
                    })

                if holdings:
                    upsert_fund_holdings(code, report_date, holdings)
                    total += len(holdings)
            except Exception as e:
                print(f"[fund_holding] {code} error: {e}")
                continue

        print(f"[fund_holding] {total} holding records for {len(self.TARGET_CODES)} ETFs")
        return total
