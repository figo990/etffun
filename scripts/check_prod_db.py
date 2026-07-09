import duckdb

c = duckdb.connect('/home/devops/etffun_data/etf_read.duckdb')

codes = ['510050','510180','510230','510300','510330','510500','512100','512500','588080','159845','159915','159919','159922','159952']
code_list = ','.join(repr(c) for c in codes)

print("=== daily_snapshot (top 10 by date desc) ===")
r = c.execute(f"""
    SELECT code, total_shares, date
    FROM daily_snapshot
    WHERE code IN ({code_list})
    ORDER BY date DESC
    LIMIT 10
""").fetchall()
for x in r:
    print(x)

print("\n=== daily_snapshot_audit (top 10 by source_date desc) ===")
r = c.execute(f"""
    SELECT code, normalized_total_shares, source_date, source_name, quality_flags
    FROM daily_snapshot_audit
    WHERE code IN ({code_list})
    ORDER BY source_date DESC
    LIMIT 10
""").fetchall()
for x in r:
    print(x)

print("\n=== Latest data per code ===")
r = c.execute(f"""
    SELECT code, MAX(source_date) as latest_date
    FROM daily_snapshot_audit
    WHERE code IN ({code_list})
    GROUP BY code
    ORDER BY code
""").fetchall()
for x in r:
    print(x)

print("\n=== Task status ===")
r = c.execute("""
    SELECT task_name, last_status, last_run_at, next_run_at
    FROM task_status
    WHERE task_name IN ('sync_db', 'huijin_audit', 'shares_sse', 'shares_szse')
    ORDER BY last_run_at DESC
    LIMIT 10
""").fetchall()
for x in r:
    print(x)

c.close()
