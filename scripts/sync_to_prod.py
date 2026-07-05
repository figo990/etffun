#!/usr/bin/env python
"""增量同步本地数据到生产库，不覆盖生产库已有的数据。
Usage: python scripts/sync_to_prod.py <production_db_path> [--dry-run]
"""
import os, sys, duckdb

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print('Usage: python scripts/sync_to_prod.py <production_db_path> [--dry-run]')
        print('Example: python scripts/sync_to_prod.py /data/etf.duckdb')
        sys.exit(0)

    PROD_DB = os.path.abspath(sys.argv[1])
    DRY_RUN = '--dry-run' in sys.argv
    LOCAL_DB = os.environ.get('ETF_DB_PATH') or os.path.join(
        os.path.dirname(__file__), '..', 'data', 'etf.duckdb')
    LOCAL_DB = os.path.abspath(LOCAL_DB)

    if not os.path.exists(LOCAL_DB):
        print(f'ERROR: Local DB not found at {LOCAL_DB}')
        sys.exit(1)
    if not os.path.exists(PROD_DB):
        print(f'ERROR: Production DB not found at {PROD_DB}')
        sys.exit(1)
    if os.path.samefile(LOCAL_DB, PROD_DB):
        print('ERROR: Local and production DB are the same file!')
        sys.exit(1)

    print(f'Local DB:  {LOCAL_DB}')
    print(f'Prod DB:   {PROD_DB}')
    print(f'Mode:      {"DRY RUN (no changes)" if DRY_RUN else "LIVE"}')
    print()

    prod = duckdb.connect(PROD_DB)

    # Attach local DB as read-only
    prod.execute(f"ATTACH '{LOCAL_DB}' AS local_db (READ_ONLY)")

    HUIJIN_CODES = ['510050','510300','159919','510330','510500','512500','159922',
                    '512100','159845','159915','159952','588080','510180','510230','588000']
    codes_placeholders = ','.join('?' for _ in HUIJIN_CODES)

    # ─── 1. daily_kline 增量同步（仅汇金 ETF） ───
    before = prod.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    if DRY_RUN:
        to_add = prod.execute(f"""
            SELECT COUNT(*) FROM local_db.daily_kline l
            WHERE l.code IN ({codes_placeholders})
              AND NOT EXISTS (SELECT 1 FROM daily_kline p WHERE p.date = l.date AND p.code = l.code)
        """, HUIJIN_CODES).fetchone()[0]
        print(f'  daily_kline: current={before}, would_add={to_add}')
    else:
        prod.execute(f"""
            INSERT INTO daily_kline (date, code, open, high, low, close, volume, amount, amplitude, turnover)
            SELECT l.date, l.code, l.open, l.high, l.low, l.close, l.volume, l.amount, l.amplitude, l.turnover
            FROM local_db.daily_kline l
            WHERE l.code IN ({codes_placeholders})
              AND NOT EXISTS (SELECT 1 FROM daily_kline p WHERE p.date = l.date AND p.code = l.code)
        """, HUIJIN_CODES)
        after = prod.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
        print(f'  daily_kline: {before} -> {after} (added {after-before})')

    # ─── 2. daily_snapshot_audit 修复 ───
    remaining = prod.execute("""
        SELECT COUNT(*) FROM daily_snapshot_audit
        WHERE source_name = 'legacy_daily_snapshot'
          AND quality_flags LIKE '%UNIT_UNVERIFIED%'
    """).fetchone()[0]
    if DRY_RUN:
        print(f'  audit UNIT_UNVERIFIED: {remaining} rows to fix')
    else:
        prod.execute("""
            UPDATE daily_snapshot_audit
            SET raw_unit = '份',
                quality_flags = 'SOURCE_AUDIT_BACKFILLED'
            WHERE source_name = 'legacy_daily_snapshot'
              AND quality_flags LIKE '%UNIT_UNVERIFIED%'
        """)
        fixed = remaining - prod.execute("""
            SELECT COUNT(*) FROM daily_snapshot_audit
            WHERE source_name = 'legacy_daily_snapshot'
              AND quality_flags LIKE '%UNIT_UNVERIFIED%'
        """).fetchone()[0]
        print(f'  audit UNIT_UNVERIFIED: fixed {fixed} rows')

    # ─── 3. 验证汇金基准 ───
    bl = prod.execute("""
        SELECT code, verification_status, is_active FROM huijin_baseline ORDER BY code
    """).fetchall()
    ok = sum(1 for b in bl if b[1] == 'verified' and b[2])
    print(f'  Huijin baselines: {ok}/{len(bl)} verified+active')

    prod.execute("DETACH local_db")
    prod.close()
    print('\nSync complete.')

if __name__ == '__main__':
    main()