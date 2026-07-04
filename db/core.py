import duckdb
import pandas as pd
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'etf.duckdb')
os.makedirs(DATA_DIR, exist_ok=True)


def get_conn(read_only=False):
    return duckdb.connect(DB_PATH, read_only=read_only)


def query(sql, params=None, max_retries=3, retry_delay=0.5):
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_conn(read_only=True)
            if params:
                result = conn.execute(sql, params).fetchdf()
            else:
                result = conn.execute(sql).fetchdf()
            conn.close()
            return result
        except duckdb.IOException as e:
            if conn is not None:
                conn.close()
            if 'Could not set lock' in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise
        except Exception:
            if conn is not None:
                conn.close()
            raise


def query_one(sql, params=None, max_retries=3, retry_delay=0.5):
    try:
        row = query(sql, params, max_retries, retry_delay).iloc[0].to_dict()
        for k, v in row.items():
            if isinstance(v, pd.Timestamp):
                row[k] = v.strftime('%Y-%m-%d')
            elif isinstance(v, float) and pd.isna(v):
                row[k] = None
        return row
    except IndexError:
        return None


def execute(sql, params=None):
    conn = get_conn(read_only=False)
    try:
        if params:
            conn.execute(sql, params)
        else:
            conn.execute(sql)
    finally:
        conn.close()


def execute_many(sql, params_list):
    if not params_list:
        return
    conn = get_conn(read_only=False)
    try:
        conn.execute("BEGIN TRANSACTION")
        conn.executemany(sql, params_list)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _to_records(df):
    df = df.where(pd.notna(df), None)
    records = df.to_dict('records')
    for row in records:
        for k, v in row.items():
            if isinstance(v, pd.Timestamp):
                row[k] = v.strftime('%Y-%m-%d')
            elif pd.isna(v) if isinstance(v, float) else False:
                row[k] = None
    return records
