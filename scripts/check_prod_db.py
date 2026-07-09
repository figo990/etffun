import duckdb

c = duckdb.connect('/home/devops/etffun_data/etf_read.duckdb')

codes = ('510050','510300','510500','512100','512500','588080','510180','510230','510330')
r = c.execute(f"""
    SELECT code, normalized_total_shares, source_date, source_name
    FROM daily_snapshot_audit
    WHERE code IN {codes}
    ORDER BY code, source_date DESC
""").fetchall()

print("=== SSE daily_snapshot_audit ===")
for x in r:
    print(x)

# Also check if write DB has newer data
c2 = duckdb.connect('/home/devops/etffun_data/etf.duckdb')
r2 = c2.execute(f"""
    SELECT code, normalized_total_shares, source_date, source_name
    FROM daily_snapshot_audit
    WHERE code IN {codes}
    ORDER BY code, source_date DESC
""").fetchall()
print("\n=== SSE daily_snapshot_audit (WRITE DB) ===")
for x in r2:
    print(x)

# Check last shares_sse task run output
r3 = c2.execute("""
    SELECT task_name, last_status, last_run_at, last_error
    FROM task_status
    WHERE task_name IN ('shares_sse', 'shares_szse')
    ORDER BY last_run_at DESC
    LIMIT 5
""").fetchall()
print("\n=== Task status ===")
for x in r3:
    print(x)

c.close()
c2.close()
