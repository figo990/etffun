import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['COLLECTOR_ROOT'] = os.path.join(os.path.dirname(__file__), '..')

from collector.tasks.shares_sse import SharesSSETask
t = SharesSSETask()
print('SSE task:', t.name, 'enabled:', t.enabled)

from collector.tasks.shares_szse import SZSESharesTask
t2 = SZSESharesTask()
print('SZSE task:', t2.name, 'enabled:', t2.enabled)
