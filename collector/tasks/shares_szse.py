import pandas as pd
import io
import requests
import time
import warnings
from datetime import datetime
from db import upsert_snapshots, batch_update_fund
from ..task_base import BaseTask


def _fetch_szse_via_http(retries=5):
    """Fetch SZSE ETF share data via official API with retry + backoff."""
    url = "https://fund.szse.cn/api/report/ShowReport"
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "1000_lf",
        "TABKEY": "tab1",
        "random": "0.07610353191740105"
    }
    headers = {
        "Referer": "https://fund.szse.cn/marketdata/fundslist/index.html",
        "User-Agent": "Mozilla/5.0"
    }
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=90)
            r.raise_for_status()
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                df = pd.read_excel(io.BytesIO(r.content), engine="openpyxl",
                                   dtype={"基金代码": str})
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"  [shares_szse] attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
    return None


def _fetch_szse_via_akshare():
    """Fallback: fetch SZSE ETF shares via akshare."""
    try:
        import akshare as ak
        df = ak.fund_etf_scale_szse()
        if df is not None and not df.empty:
            df = df.rename(columns={
                '基金代码': '基金代码', '基金简称': '基金简称',
                '基金份额': '基金份额', '净值': '净值'
            })
            return df
    except Exception as e:
        print(f"  [shares_szse] akshare fallback failed: {e}")
    return None


class SharesSZSECTask(BaseTask):
    task_name = 'shares_szse'
    display_name = '深交所ETF份额'

    def _execute(self):
        df = _fetch_szse_via_http(retries=5)
        if df is None:
            print("  [shares_szse] HTTP failed, trying akshare fallback...")
            df = _fetch_szse_via_akshare()
        if df is None:
            raise RuntimeError("SZSE scale data unavailable from all sources")

        rename_map = {}
        for col in df.columns:
            c = str(col).strip()
            if '规模' in c and '份' in c:
                rename_map[col] = '基金份额'
            elif '简称' in c or '名称' in c:
                rename_map[col] = '基金简称'
        df = df.rename(columns=rename_map)

        if '基金份额' not in df.columns:
            raise RuntimeError("SZSE data missing '基金份额' column")
        if '净值' not in df.columns:
            df['净值'] = None

        temp_df = df[['基金代码', '基金简称', '基金份额', '净值']].copy()
        temp_df["基金份额"] = (
            temp_df["基金份额"].astype(str).str.replace(",", "", regex=False)
        )
        temp_df["基金份额"] = pd.to_numeric(temp_df["基金份额"], errors="coerce")
        temp_df["净值"] = pd.to_numeric(temp_df["净值"], errors="coerce")

        today_str = datetime.now().strftime('%Y%m%d')
        today_date = datetime.now().strftime('%Y-%m-%d')
        snap_rows = []
        fund_rows = []
        for _, row in temp_df.iterrows():
            code = str(row['基金代码'])
            total_shares = float(row['基金份额']) if pd.notna(row['基金份额']) else None
            nav_val = float(row['净值']) if pd.notna(row['净值']) else None
            name = row['基金简称']
            snap_rows.append((code, total_shares, None, None, None, None, None, nav_val, today_date))
            fund_rows.append((code, name, '深'))

        if snap_rows:
            upsert_snapshots(today_str, snap_rows)
            batch_update_fund(fund_rows)

        count = len(snap_rows)
        print(f"[shares_szse] {today_str}: {count} records")
        return count
