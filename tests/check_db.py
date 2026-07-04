"""Check local DB state"""
import sys
sys.path.insert(0, 'E:\\code\\etffun')

from db.core import get_conn, DB_PATH
print(f'DB_PATH: {DB_PATH}')

conn = get_conn(read_only=True)
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'").fetchall()
for t in tables:
    name = t[0]
    count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    print(f'  {name}: {count} rows')
conn.close()