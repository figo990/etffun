from db import (
    DB_PATH,
    READ_DB_PATH,
    backfill_huijin_daily_snapshot_audit,
    bootstrap_huijin_support_data,
    sync_tables,
)
from ..task_base import BaseTask


class HuijinAuditTask(BaseTask):
    task_name = 'huijin_audit'
    display_name = '汇金数据审计'

    def _execute(self):
        backfilled = backfill_huijin_daily_snapshot_audit()
        result = bootstrap_huijin_support_data(refresh_issues=True, sync_read=True)
        if backfilled and DB_PATH != READ_DB_PATH:
            result['synced_tables'] += sync_tables(['daily_snapshot_audit'])
        print(
            "[huijin_audit] "
            f"draft_baselines={result.get('draft_baselines', 0)} "
            f"watch_groups={result.get('watch_groups', 0)} "
            f"calendar={result.get('market_calendar', 0)} "
            f"legacy_audit={backfilled} "
            f"quality_issues={result.get('quality_issues', 0)} "
            f"synced_tables={result.get('synced_tables', 0)}"
        )
        return result.get('quality_issues', 0)
