from datetime import datetime, timedelta

import akshare as ak

from db import (
    DB_PATH,
    READ_DB_PATH,
    create_data_source_run,
    finish_data_source_run,
    get_max_date,
    seed_market_calendar_from_trading_dates,
    sync_tables,
)
from ..task_base import BaseTask


class MarketCalendarTask(BaseTask):
    task_name = 'market_calendar'
    display_name = '交易日历'

    def _execute(self):
        run_id = create_data_source_run(self.task_name, 'sina_trade_calendar')
        try:
            df = ak.tool_trade_date_hist_sina()
            if df is None or df.empty or 'trade_date' not in df.columns:
                raise RuntimeError('Sina trade calendar unavailable')
            dates = [str(v) for v in df['trade_date'].dropna().tolist()]
            as_of = _parse_ymd(get_max_date() or datetime.now().strftime('%Y-%m-%d'))
            start = (as_of - timedelta(days=760)).strftime('%Y-%m-%d')
            end = (as_of + timedelta(days=370)).strftime('%Y-%m-%d')
            count = seed_market_calendar_from_trading_dates(dates, start, end)
            finish_data_source_run(run_id, 'success', count)
            synced = 0
            if DB_PATH != READ_DB_PATH:
                synced = sync_tables(['market_calendar', 'data_source_run'])
            print(f"[market_calendar] seeded {count} rows synced_tables={synced}")
            return count
        except Exception as e:
            finish_data_source_run(run_id, 'failed', 0, str(e))
            raise


def _parse_ymd(value):
    if hasattr(value, 'strftime'):
        value = value.strftime('%Y-%m-%d')
    return datetime.strptime(str(value)[:10], '%Y-%m-%d')
