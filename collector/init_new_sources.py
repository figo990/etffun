"""
新数据源初始化脚本
首次部署时运行一次，抓取历史数据并初始化新增表。

使用方法: python -m collector.init_new_sources
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db

def main():
    print("=" * 50)
    print("  新数据源初始化")
    print("=" * 50)

    print("\n[1/5] 初始化数据库表结构...")
    init_db()
    print("  ✓ 表结构就绪")

    print("\n[2/5] 抓取北向资金历史数据(近60个交易日)...")
    try:
        from collector.tasks.northbound import NorthboundTask
        task = NorthboundTask()
        task._execute()
        print("  ✓ 北向资金数据就绪")
    except Exception as e:
        print(f"  ✗ 北向资金抓取失败: {e}")
        print("    (可能是网络问题，后续调度会自动重试)")

    print("\n[3/5] 抓取ETF期权数据...")
    try:
        from collector.tasks.etf_option import EtfOptionTask
        task = EtfOptionTask()
        task._execute()
        print("  ✓ ETF期权数据就绪")
    except Exception as e:
        print(f"  ✗ ETF期权抓取失败: {e}")
        print("    (可能是网络问题或非交易时段，后续调度会自动重试)")

    print("\n[4/5] 抓取核心ETF持仓数据(TOP20 ETF)...")
    try:
        from collector.tasks.fund_holding import HoldingTask
        task = HoldingTask()
        task._execute()
        print("  ✓ ETF持仓数据就绪")
    except Exception as e:
        print(f"  ✗ ETF持仓抓取失败: {e}")
        print("    (可能是网络问题，后续调度会自动重试)")

    print("\n[5/5] 抓取机构持仓比例(前50只ETF)...")
    try:
        from collector.tasks.inst_hold import InstHoldTask
        task = InstHoldTask()
        task._execute()
        print("  ✓ 机构持仓数据就绪")
    except Exception as e:
        print(f"  ✗ 机构持仓抓取失败: {e}")
        print("    (可能是网络问题，后续调度会自动重试)")

    print("\n" + "=" * 50)
    print("  初始化完成！")
    print("  - 成功的数据源立即可用")
    print("  - 失败的数据源将在调度任务启动后自动重试")
    print("  - 运行 start_collector.bat 启动定时采集")
    print("=" * 50)


if __name__ == '__main__':
    main()
