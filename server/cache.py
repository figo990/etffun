import time
import duckdb
from db import get_all_etf, get_stats, get_task_status_all


class DataCache:
    def __init__(self, ttl=30, stale_ttl=300):
        self._etf_all = None
        self._etf_all_ts = 0
        self._stats = None
        self._stats_ts = 0
        self._tasks = None
        self._tasks_ts = 0
        self._ttl = ttl
        self._stale_ttl = stale_ttl

    def _is_expired(self, timestamp):
        return time.time() - timestamp > self._ttl

    def _is_stale(self, timestamp):
        return time.time() - timestamp > self._stale_ttl

    def configure(self, ttl=None, stale_ttl=None):
        if ttl is not None:
            self._ttl = int(ttl)
        if stale_ttl is not None:
            self._stale_ttl = int(stale_ttl)

    def _fetch(self, getter, cache_attr, ts_attr, force=False):
        cached = getattr(self, cache_attr)
        ts = getattr(self, ts_attr)
        if force or cached is None or self._is_expired(ts):
            try:
                fresh = getter()
                setattr(self, cache_attr, fresh)
                setattr(self, ts_attr, time.time())
                return fresh
            except duckdb.IOException:
                # DB locked: serve stale data if available and not too old
                if cached is not None and not self._is_stale(ts):
                    return cached
                raise
        return cached

    def get_etf_all(self, force=False):
        return self._fetch(get_all_etf, '_etf_all', '_etf_all_ts', force)

    def get_stats(self, force=False):
        return self._fetch(get_stats, '_stats', '_stats_ts', force)

    def get_tasks(self, force=False):
        return self._fetch(get_task_status_all, '_tasks', '_tasks_ts', force)

    def invalidate(self):
        self._etf_all_ts = 0
        self._stats_ts = 0
        self._tasks_ts = 0


cache = DataCache(ttl=30)
