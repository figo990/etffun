import akshare as ak
import pandas as pd
from datetime import datetime
from db import upsert_sector_fund_flow
from ..task_base import BaseTask

PERIOD_SYMBOLS = {
    '1d': '即时',
    '3d': '3日排行',
    '5d': '5日排行',
    '10d': '10日排行',
    '20d': '20日排行',
}
# Weekly periods to collect in addition to '1d' (only on Monday)
WEEKLY_PERIODS = ['3d', '5d', '10d', '20d']


def _collect_ths(period_key, symbol):
    """Collect from 同花顺, return list of tuples or None."""
    try:
        df = ak.stock_fund_flow_industry(symbol=symbol)
        if df is not None and not df.empty:
            today = datetime.now().strftime('%Y-%m-%d')
            rows = []
            for _, row in df.iterrows():
                rows.append((
                    today,
                    str(row.get('行业', '')),
                    float(row.get('净额', 0) or 0),
                    None, None, None, None,
                ))
            return rows
    except Exception as e:
        print(f"  [sector_fund_flow] THS {symbol} failed: {e}")
    return None


class SectorFundFlowTask(BaseTask):
    task_name = 'sector_fund_flow'
    display_name = '行业资金流向'

    def _execute(self):
        today = datetime.now().strftime('%Y-%m-%d')
        weekday = datetime.now().weekday()
        is_monday = weekday == 0
        periods_to_collect = ['1d']
        if is_monday:
            periods_to_collect += WEEKLY_PERIODS
            print(f"  [sector_fund_flow] Monday: collecting multi-period data", flush=True)

        for period_key in periods_to_collect:
            symbol = PERIOD_SYMBOLS[period_key]
            rows = []

            # Primary: EM API (has full breakdown)
            if period_key == '1d':
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
                    print(f"  [sector_fund_flow] EM API failed: {e}")

            # Fallback: THS
            if not rows:
                rows = _collect_ths(period_key, symbol)

            if rows:
                upsert_sector_fund_flow(rows, period=period_key)
                print(f"  [sector_fund_flow] {period_key}: {len(rows)} sectors")
            else:
                print(f"  [sector_fund_flow] {period_key}: no data")

        return 1