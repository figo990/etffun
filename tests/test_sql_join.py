"""Test: get_all_etf SQL with new JOINs (uses main DB)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.core import execute, query, get_conn
from db.schema import init_db
init_db()

# Clean up any leftover test data first
execute("DELETE FROM fund WHERE code = 'TEST99'")
execute("DELETE FROM daily_snapshot WHERE code = 'TEST99'")
execute("DELETE FROM index_valuation WHERE index_code = 'TEST99'")
execute("DELETE FROM margin_detail WHERE code = 'TEST99'")

execute("INSERT INTO fund VALUES ('TEST99','TEST99ETF','沪',NULL,'华夏基金','TEST99','测试指数',NULL)")
execute("INSERT INTO daily_snapshot (date,code,total_shares,price,turnover) VALUES ('2026-07-03','TEST99',100000000,2.5,50000000)")
execute("INSERT INTO daily_snapshot (date,code,total_shares) VALUES ('2026-07-02','TEST99',90000000)")
execute("INSERT INTO index_valuation VALUES ('2026-07-03','TEST99','测试指数',10.5,1.2,3.0,48.0,35.0)")
execute("INSERT INTO margin_detail VALUES ('2026-07-03','TEST99',1000000000,50000000,30000000,20000000,5000000)")

from db.queries import get_all_etf
data = get_all_etf()
test_item = [d for d in data if d['代码'] == 'TEST99']

if test_item:
    item = test_item[0]
    print('SQL JOIN test OK')
    for k in ['代码','名称','市盈率PE','市净率PB','PE历史分位','PB历史分位','融资余额_亿','融资净买入_亿']:
        v = item.get(k)
        print(f'  {k}: {v}')
else:
    print('WARNING: Test item not found in results')

# Clean up
execute("DELETE FROM fund WHERE code = 'TEST99'")
execute("DELETE FROM daily_snapshot WHERE code = 'TEST99'")
execute("DELETE FROM index_valuation WHERE index_code = 'TEST99'")
execute("DELETE FROM margin_detail WHERE code = 'TEST99'")
print('Test data cleaned up')