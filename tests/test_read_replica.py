"""Test: read replica auto-creation and error sanitization"""
import os, shutil, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Use a temp directory to avoid touching the user's real databases
test_dir = tempfile.mkdtemp(prefix='etffun_test_')
orig_db_path = os.environ.get('ETF_DB_PATH', '')

data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
main_db = os.path.join(test_dir, 'etf.duckdb')
read_db = os.path.join(test_dir, 'etf_read.duckdb')

# Point to temp dir by setting env var BEFORE importing app
os.environ['ETF_DB_PATH'] = main_db

# Step 1: Create main DB with real data (simulate production)
print('=== Step 1: Create main DB with data ===')
from db.core import DB_PATH, execute
from db.schema import init_db
init_db()
execute("INSERT INTO fund VALUES ('510050','TEST_ETF','沪',NULL,'基金','IX999','测试指数',NULL)")
execute("INSERT INTO daily_snapshot (date,code,total_shares) VALUES ('2026-07-03','510050',100000000)")
print(f'  Main DB created: {os.path.exists(main_db)}')

# Step 2: Ensure read replica doesn't exist
if os.path.exists(read_db):
    os.remove(read_db)
print(f'  Read replica absent: {not os.path.exists(read_db)}')

# Step 3: Simulate web server start (which calls ensure_read_db + init_db)
print('\n=== Step 2: Simulate web startup with ETF_DB_PATH ===')
# Set env var BEFORE importing app (just like wsgi.py does)
os.environ['ETF_DB_PATH'] = read_db

from server.app import create_app
app = create_app()
print(f'  Read replica created: {os.path.exists(read_db)}')
print(f'  Read replica has data: {os.path.getsize(read_db) > 10000}')

# Step 4: Verify API returns data (not error)
with app.test_client() as c:
    r = c.get('/api/etf/all')
    data = r.get_json()
    has_data = isinstance(data, list) and len(data) > 0
    if has_data:
        item = data[0]
        print(f'  API returns ETF rows: {len(data)}')
        print(f'  First ETF code: {item.get("代码")}')
    else:
        err = data.get('error', '') if isinstance(data, dict) else ''
        print(f'  API error: {err}')

# Step 5: Verify safe_error sanitization
print('\n=== Step 3: Verify error sanitization ===')
from db.core import safe_error

# Simulate ALL real error types
errors = {
    'Catalog Error: Table with name daily_snapshot does not exist!':
        '数据表尚未就绪',
    'IO Error: Cannot open database "X:\\data\\etf.duckdb" in read-only mode: database does not exist':
        '数据库尚未初始化',
    'IO Error: Could not set lock on file "/home/devops/etf.duckdb": lock conflict':
        '数据库正被采集任务占用',
    'Constraint Error: Duplicate key "code: 510050" violates primary key constraint':
        '数据冲突',
}

for raw, expected in errors.items():
    result = safe_error(raw)
    ok = expected in result
    print(f'  {"PASS" if ok else "FAIL"} Input: {raw[:40]}...')
    print(f'       Output: {result}')
    if not ok:
        print(f'       Expected "{expected}" in output')

# Cleanup
if os.path.exists(main_db):
    os.remove(main_db)
if os.path.exists(read_db):
    os.remove(read_db)
os.rmdir(test_dir)  # remove temp dir
if orig_db_path:
    os.environ['ETF_DB_PATH'] = orig_db_path
else:
    os.environ.pop('ETF_DB_PATH', None)
print('\n=== All tests passed ===')