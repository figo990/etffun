import time
import functools
from .status_writer import StatusWriter


def retry(max_attempts=3, delay=2):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (attempt + 1))
            raise last_exc
        return wrapper
    return decorator


class BaseTask:
    task_name = ''
    display_name = ''

    def run(self):
        with StatusWriter(self.task_name) as sw:
            self._execute()

    def _execute(self):
        raise NotImplementedError
