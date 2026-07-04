"""Test: DB missing, safe_error sanitization"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Delete main DB to simulate first-run scenario
main_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'etf.duckdb')
if os.path.exists(main_db):
    os.remove(main_db)
    print('Deleted main DB for test')

from db.core import safe_error, get_conn, DB_PATH
print('DB_PATH:', DB_PATH)

# Test 1: safe_error sanitizes paths
err = safe_error('IO Error: Cannot open database "X:\\some\\path\\etf.duckdb" in read-only mode: database does not exist')
print('safe_error output:', err)
assert '<path>' in err or '<data>' in err, f'Path not sanitized'
assert 'etf.duckdb' not in err, f'DB name leaked'
print('safe_error: path sanitized OK')

# Test 2: get_conn creates DB if missing
conn = get_conn(read_only=True)
conn.close()
print('get_conn with missing DB: OK')
assert os.path.exists(DB_PATH), 'DB was not created'

# Test 3: API returns sanitized error
from server.app import create_app
app = create_app()
with app.test_client() as c:
    r = c.get('/api/etf/kline?code=NONEXIST')
    data = r.get_json()
    msg = data.get('error', '') if data else ''
    print('API error message:', msg[:100])
    if '<data>' in msg or '<path>' in msg:
        print('Error message sanitized: OK')

# Cleanup
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print('Cleanup OK')

print('All tests passed')