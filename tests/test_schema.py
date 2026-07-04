"""Test: schema initialization and new tables"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ETF_DB_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_etf.duckdb')

from db.schema import init_db
init_db()
print('Schema initialized OK')

from db.core import get_conn
conn = get_conn()
tables = [r[0] for r in conn.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
).fetchall()]
conn.close()
print('Tables:', tables)

expected = {'fund','daily_snapshot','index_spot','task_status','task_trigger',
            'fund_holding','northbound_flow','etf_option','task_history',
            'daily_kline','sector_fund_flow','index_valuation','bond_yield','margin_detail'}
missing = expected - set(tables)
if missing:
    print(f'MISSING: {missing}')
else:
    print('All 14 tables OK')