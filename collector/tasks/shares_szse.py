import pandas as pd
import io
import requests
import warnings
from datetime import datetime
from db import upsert_snapshots, batch_update_fund
from ..task_base import BaseTask


class SharesSZSECTask(BaseTask):
    task_name = 'shares_szse'
    display_name = '深交所ETF份额'

    def _execute(self):
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
        r = requests.get(url, params=params, headers=headers, timeout=30)

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            temp_df = pd.read_excel(io.BytesIO(r.content), engine="openpyxl",
                                    dtype={"基金代码": str})

        temp_df.rename(columns={"当前规模(份)": "基金份额"}, inplace=True)
        temp_df = temp_df[["基金代码", "基金简称", "基金份额", "净值"]]
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
