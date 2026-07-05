#!/usr/bin/env python
"""Sync locally collected data (K-line, audit fixes) to production DB.
Usage: python scripts/sync_to_prod.py <production_db_path>
"""
import os, sys, duckdb

if len(sys.argv) < 2:
    print('Usage: python scripts/sync_to_prod.py <production_db_path>')
    print('Example: python scripts/sync_to_prod.py /path/to/prod/etf.duckdb')
    sys.exit(1)

PROD_DB = sys.argv[1]
LOCAL_DB = os.environ.get('ETF_DB_PATH') or os.path.join(os.path.dirname(__file__), '..', 'data', 'etf.duckdb')

if not os.path.exists(LOCAL_DB):
    print(f'ERROR: Local DB not found at {LOCAL_DB}')
    sys.exit(1)
if not os.path.exists(PROD_DB):
    print(f'ERROR: Production DB not found at {PROD_DB}')
    sys.exit(1)

print(f'Local DB:  {LOCAL_DB}')
print(f'Prod DB:   {PROD_DB}')

# Sync K-line data for Huijin ETFs
HUIJIN_CODES = ['510050','510300','159919','510330','510500','512500','159922',
                '512100','159845','159915','159952','588080','510180','510230','588000']

codes_sql = ','.join(f"'{c}'" for c in HUIJIN_CODES)

prod = duckdb.connect(PROD_DB)

# 1. Sync daily_kline for Huijin codes
prod.execute(f"""
    INSERT INTO daily_kline (date, code, open, high, low, close, volume, amount, amplitude, turnover)
    SELECT l.date, l.code, l.open, l.high, l.low, l.close, l.volume, l.amount, l.amplitude, l.turnover
    FROM '{LOCAL_DB}' l.daily_kline l
    WHERE l.code IN ({codes_sql})
    ON CONFLICT (date, code) DO NOTHING
""")
kline_count = prod.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
print(f'  daily_kline: {kline_count} total rows')

# 2. Sync daily_snapshot_audit fixes
prod.execute("""
    UPDATE daily_snapshot_audit
    SET raw_unit = '份',
        quality_flags = 'SOURCE_AUDIT_BACKFILLED'
    WHERE source_name = 'legacy_daily_snapshot'
      AND quality_flags LIKE '%UNIT_UNVERIFIED%'
""")
audit_count = prod.execute("SELECT COUNT(*) FROM daily_snapshot_audit WHERE quality_flags LIKE '%UNIT_UNVERIFIED%'").fetchone()[0]
print(f'  Remaining UNIT_UNVERIFIED: {audit_count} (should be 0)')

# 3. Verify huijin baselines
bl = prod.execute("SELECT code, verification_status, is_active FROM huijin_baseline ORDER BY code").fetchall()
ok = sum(1 for b in bl if b[1] == 'verified' and b[2])
print(f'  Huijin baselines: {ok}/{len(bl)} verified+active')

prod.close()
print('\nSync complete.')