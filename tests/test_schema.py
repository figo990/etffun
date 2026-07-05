"""Test: schema initialization and new tables"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ETF_DB_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_etf.duckdb')
os.environ['ETF_READ_DB_PATH'] = os.environ['ETF_DB_PATH']

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
            'daily_kline','sector_fund_flow','index_valuation','bond_yield','margin_detail',
            'huijin_baseline','huijin_baseline_holder',
            'daily_snapshot_audit','market_calendar','data_source_run',
            'data_quality_issue','fund_share_event','huijin_watch_group',
            'cffex_position_rank'}
missing = expected - set(tables)
if missing:
    print(f'MISSING: {missing}')
else:
    print('All 23 tables OK')

conn = get_conn()
columns = {
    r[1]: r[2] for r in conn.execute("PRAGMA table_info('huijin_baseline')").fetchall()
}
holder_columns = {
    r[1]: r[2] for r in conn.execute("PRAGMA table_info('huijin_baseline_holder')").fetchall()
}
audit_columns = {
    r[1]: r[2] for r in conn.execute("PRAGMA table_info('daily_snapshot_audit')").fetchall()
}
issue_columns = {
    r[1]: r[2] for r in conn.execute("PRAGMA table_info('data_quality_issue')").fetchall()
}
cffex_columns = {
    r[1]: r[2] for r in conn.execute("PRAGMA table_info('cffex_position_rank')").fetchall()
}
conn.close()

for col in ['baseline_id','code','report_period','report_date','disclosure_date',
            's0_total_shares','h0_total_shares','a_ratio','verification_status','is_active']:
    assert col in columns, f'huijin_baseline missing {col}'
for col in ['baseline_id','holder_name','holder_group','holder_shares','holder_ratio','source_line']:
    assert col in holder_columns, f'huijin_baseline_holder missing {col}'
for col in ['date','code','source_name','source_date','source_date_inferred',
            'raw_total_shares','raw_unit','normalized_total_shares','run_id','quality_flags']:
    assert col in audit_columns, f'daily_snapshot_audit missing {col}'
for col in ['issue_id','code','date','issue_type','severity','status','message','created_at']:
    assert col in issue_columns, f'data_quality_issue missing {col}'
for col in ['date','contract','rank_type','rank_no','member_name','volume','change','source_name','run_id']:
    assert col in cffex_columns, f'cffex_position_rank missing {col}'
print('Huijin baseline columns OK')
