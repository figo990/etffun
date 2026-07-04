import akshare as ak
import pandas as pd
from datetime import datetime
from db import execute_many
from ..task_base import BaseTask

MAX_CODES = 80


def _to_sina_symbol(code):
    if code.startswith(('5', '6')):
        return f"sh{code}"
    return f"sz{code}"


class BackfillPricesTask(BaseTask):
    task_name = 'backfill_prices'
    display_name = '历史价格回填'

    def _execute(self):
        from db import get_conn
        today_str = datetime.now().strftime('%Y-%m-%d')

        conn = get_conn(read_only=True)
        try:
            codes = [r[0] for r in conn.execute("""
                SELECT d.code
                FROM daily_snapshot d
                JOIN fund f ON f.code = d.code
                WHERE d.total_shares IS NOT NULL AND d.price IS NULL
                  AND (d.code LIKE '51%' OR d.code LIKE '159%' OR d.code LIKE '588%' OR d.code LIKE '518%')
                GROUP BY d.code
                HAVING COUNT(*) > 5
                ORDER BY MAX(f.huijin_亿) DESC NULLS LAST, COUNT(*) DESC
                LIMIT ?
            """, [MAX_CODES]).fetchall()]
        finally:
            conn.close()

        if not codes:
            print("[backfill_prices] no codes need backfill")
            return 0

        total = 0
        for code in codes:
            try:
                symbol = _to_sina_symbol(code)
                df = ak.fund_etf_hist_sina(symbol=symbol)
                if df is None or df.empty:
                    continue

                updates = []
                for _, row in df.iterrows():
                    d = str(row['date'])[:10]
                    close = float(row['close']) if pd.notna(row.get('close')) else None
                    amount = float(row['amount']) if pd.notna(row.get('amount')) else None
                    if close is not None:
                        updates.append((close, amount, code, d))

                if updates:
                    execute_many("""
                        UPDATE daily_snapshot
                        SET price = COALESCE(price, ?), turnover = COALESCE(turnover, ?)
                        WHERE code = ? AND date = CAST(? AS DATE)
                    """, updates)
                    total += len(updates)
            except Exception as e:
                print(f"  [backfill_prices] {code} error: {e}")
                continue

        print(f"[backfill_prices] filled {total} price records")
        return total
