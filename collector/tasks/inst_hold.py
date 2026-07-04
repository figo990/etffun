import pandas as pd
from db import update_fund_inst_hold
from db.core import query
from ..task_base import BaseTask


class InstHoldTask(BaseTask):
    """
    机构持仓比例采集任务。
    注意：当前 akshare 版本无 fund_report_holder_em 接口，
    此任务默认 disabled。待接口恢复后启用。
    """
    task_name = 'inst_hold'
    display_name = '机构持仓比例'

    def _execute(self):
        try:
            import akshare as ak
            if not hasattr(ak, 'fund_report_holder_em'):
                print("[inst_hold] akshare.fund_report_holder_em 不可用，跳过")
                return 0
        except ImportError:
            print("[inst_hold] akshare 未安装")
            return 0

        funds_df = query("SELECT code FROM fund")
        codes = funds_df['code'].tolist() if not funds_df.empty else []

        updated = 0
        for code in codes[:200]:
            try:
                df = ak.fund_report_holder_em(symbol=code)
                if df is None or df.empty:
                    continue
                latest = df.iloc[0]
                inst_pct = latest.get('机构持有比例') or latest.get('机构投资者持有比例')
                if inst_pct is not None and pd.notna(inst_pct):
                    update_fund_inst_hold(code, float(inst_pct))
                    updated += 1
            except Exception:
                continue

        print(f"[inst_hold] updated {updated} funds with institutional hold ratio")
        return updated
