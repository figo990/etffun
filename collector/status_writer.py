import time
from datetime import datetime
from db import update_task_status, insert_task_history


class StatusWriter:
    def __init__(self, task_name):
        self.task_name = task_name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        update_task_status(self.task_name, 'running')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            error = f"{exc_type.__name__}: {exc_val}" if exc_val else str(exc_type)
            update_task_status(self.task_name, 'failed', duration, error)
            insert_task_history(self.task_name, 'failed', duration, error)
        else:
            update_task_status(self.task_name, 'success', duration)
            insert_task_history(self.task_name, 'success', duration)
        return False
