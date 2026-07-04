import duckdb
import pandas as pd
import os
import time
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.environ.get('ETF_DB_PATH') or os.path.join(DATA_DIR, 'etf.duckdb')
READ_DB_PATH = os.environ.get('ETF_READ_DB_PATH') or os.path.join(DATA_DIR, 'etf_read.duckdb')
os.makedirs(DATA_DIR, exist_ok=True)


def safe_error(e):
    """Return a user-friendly error message without internal details."""
    msg = str(e)
    if 'Could not set lock' in msg or 'lock' in msg.lower():
        return '数据库正被采集任务占用，自动重试中，请稍后刷新'
    if 'Cannot open database' in msg:
        return '数据库尚未初始化，请先运行数据采集'
    if 'does not exist' in msg.lower():
        return '数据表尚未就绪，正在同步数据，请稍后重试'
    if 'Constraint Error' in msg or 'Duplicate key' in msg:
        return '数据冲突，请刷新后重试'
    # Fallback: strip paths and technical noise
    if DATA_DIR and DATA_DIR in msg:
        msg = msg.replace(DATA_DIR, '')
    msg = re.sub(r'"[A-Z]:[^"]*"', '', msg)
    msg = re.sub(r'"/[^"]*"', '', msg)
    msg = re.sub(r'[A-Z]:\\(?:[^\\\s]+\\)*', '', msg)
    msg = re.sub(r'/[\w./-]+', '', msg)
    msg = re.sub(r'LINE\s+\d+:.*', '', msg)
    msg = re.sub(r'Did you mean[^?]+\?', '', msg)
    msg = re.sub(r'\s+', ' ', msg).strip().strip(':;,')
    return msg[:120] or '服务内部错误'


def get_conn(read_only=False):
    if read_only:
        path = READ_DB_PATH if os.path.exists(READ_DB_PATH) else DB_PATH
    else:
        path = DB_PATH
    if not os.path.exists(path):
        conn = duckdb.connect(path)
        conn.close()
    return duckdb.connect(path, read_only=read_only)


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
