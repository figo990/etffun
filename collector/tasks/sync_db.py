from db.sync import sync_all_tables
from ..task_base import BaseTask


class SyncDbTask(BaseTask):
    task_name = 'sync_db'
    display_name = 'DB读写同步'

    def _execute(self):
        count = sync_all_tables()
        print(f"[sync_db] synced {count} tables")
        return count