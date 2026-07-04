import duckdb
import pandas as pd
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.environ.get('ETF_DB_PATH') or os.path.join(DATA_DIR, 'etf.duckdb')
os.makedirs(DATA_DIR, exist_ok=True)


def get_conn(read_only=False):
    return duckdb.connect(DB_PATH, read_only=read_only)


def query(sql, params=None, max_retries=20, retry_delay=1):
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
            if 'Could not set lock' in str(e):
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
            raise
        except Exception:
            if conn is not None:
                conn.close()
            raise


def query_one(sql, params=None, max_retries=3, retry_delay=0.5):
    try:
        df = query(sql, params, max_retries, retry_delay)
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].apply(lambda v: v.strftime('%Y-%m-%d') if pd.notna(v) else None)
        row = df.iloc[0].to_dict()
        for k, v in row.items():
            if v is None or v is pd.NaT:
                row[k] = None
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
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].apply(lambda v: v.strftime('%Y-%m-%d') if pd.notna(v) and v is not pd.NaT else None)
    records = df.to_dict('records')
    for row in records:
        for k, v in row.items():
            if v is None or v is pd.NaT:
                row[k] = None
            elif isinstance(v, float) and pd.isna(v):
                row[k] = None
    return records
