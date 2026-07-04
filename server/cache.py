import time
from db import get_all_etf, get_stats, get_task_status_all


class DataCache:
    def __init__(self, ttl=30):
        self._etf_all = None
        self._etf_all_ts = 0
        self._stats = None
        self._stats_ts = 0
        self._tasks = None
        self._tasks_ts = 0
        self._ttl = ttl

    def _is_expired(self, timestamp):
        return time.time() - timestamp > self._ttl

    def configure(self, ttl=None):
        if ttl is not None:
            self._ttl = int(ttl)

    def get_etf_all(self, force=False):
        if force or self._etf_all is None or self._is_expired(self._etf_all_ts):
            self._etf_all = get_all_etf()
            self._etf_all_ts = time.time()
        return self._etf_all

    def get_stats(self, force=False):
        if force or self._stats is None or self._is_expired(self._stats_ts):
            self._stats = get_stats()
            self._stats_ts = time.time()
        return self._stats

    def get_tasks(self, force=False):
        if force or self._tasks is None or self._is_expired(self._tasks_ts):
            self._tasks = get_task_status_all()
            self._tasks_ts = time.time()
        return self._tasks

    def invalidate(self):
        self._etf_all_ts = 0
        self._stats_ts = 0
        self._tasks_ts = 0


cache = DataCache(ttl=30)
