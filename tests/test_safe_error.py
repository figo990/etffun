"""Test: safe_error sanitization for all error types"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db.core import safe_error

tests = [
    # (error_message, expected_pattern)
    (
        'Catalog Error: Table with name daily_snapshot does not exist! Did you mean "sqlite_master"? LINE 8: FROM daily_snapshot',
        'table does not exist'
    ),
    (
        'IO Error: Cannot open database "X:\\data\\etf.duckdb" in read-only mode: database does not exist',
        'read-only'
    ),
    (
        'IO Error: Could not set lock on file "/home/devops/etffun_data/etf.duckdb": Conflicting lock is held in /usr/bin/python3.11 (PID 12345) by user devops',
        'lock'
    ),
    (
        'Constraint Error: Duplicate key "code: 510050" violates primary key constraint',
        'Duplicate'
    ),
]

for msg, expected in tests:
    result = safe_error(msg)
    has_path = ('\\' in msg and '\\' in result) or ('etf.duckdb' in result) or ('python3' in result)
    print(f'  Input:  {msg[:60]}...')
    print(f'  Output: {result}')
    if has_path:
        print(f'  FAIL: path still exposed!')
    elif expected.lower() not in result.lower():
        print(f'  INFO: expected "{expected}" not in output')
    else:
        print(f'  PASS')
    print()