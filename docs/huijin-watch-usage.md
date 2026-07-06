# 汇金 ETF 份额观察使用说明

## 功能边界

本功能只基于公开 ETF 总份额和基金定期报告披露线索做份额观察与候选筛查，不确认中央汇金真实买卖，不输出个性化投资建议。

核心公式保持为:

```text
A = H0 / S0
X0 = 1 - A
B = S1 / S0
Y_min = max(0, B - (1 - A))
Y_max = B
```

其中 `H0/S0/A` 来自已核验披露基准，`S1` 来自交易所或审计后的 ETF 总份额。

## 页面使用

1. 打开“汇金观察”页签，先看顶部质量总览和问题清单。
2. `数据阻断` 样本不输出区间，不输出有效信号，默认不进入回测。
3. `质量警告` 样本可观察，但默认不进入回测；常见原因包括深市源日期推断、沪市源滞后、份额断档或异常跳变。
4. 主表中的“观察/未触发原因”用于解释增强观察、减弱观察或观望的触发逻辑；“份额变动强度”只表示当前 S1 相对披露日 S0 的变化。
5. ETF 池贡献拆解用于查看同指数组内各 ETF 对份额变化的贡献，以及组内 blocked/warning 成分。
6. 期指辅助只展示日期、合约覆盖和滞后状态，不进入核心公式。
7. 回测/复盘区只做事件研究；样本不足时显示“样本不足/仅可观察”，并列出 blocked/warning/no_signal 等跳过原因。

## 回测/复盘口径

- 严禁未来函数。
- 只使用 `disclosure_date <= 信号日` 的 verified 基准。
- T 日生成观察信号，T+1 或后续首个 K 线收盘价开始评估收益。
- 支持 5/10/20/60 个交易日观察窗口。
- 默认过滤 blocked/warning。
- warning 样本可用 `include_warnings=true` 单独观察，但默认不纳入页面复盘口径。
- 输出信号次数、方向命中率、平均收益、最大回撤；不生成直接买卖建议。

## 补齐回测数据

当回测区显示“样本不足/仅可观察”，先检查 `sample_gate` 和 `skipped_reasons`。如果主要原因是 `SOURCE_DATE_INFERRED` 或 `legacy_daily_snapshot`，运行验证式历史审计补齐:

```bash
python -m collector.tasks.backfill_shares --repair-huijin-audit --start 2025-12-31 --end 2026-07-03
```

该命令会重新拉取公开 ETF 份额源，并且只在源数据与本地 `S1` 同日同代码匹配时写入 `backfill_sse_etf_scale` / `backfill_szse_etf_scale` 审计记录。写入后同步读库:

如果问题是交易日中间缺少份额行，运行缺口补齐:

```bash
python -m collector.tasks.backfill_shares --fill-huijin-missing-shares --start 2026-04-07 --end 2026-07-01 --codes 159845,159915,159919,159922,159952
```

该命令只补 active verified baseline 披露日之后的交易日缺口，并写入公开源审计记录。

```bash
python -c "from db.sync import sync_tables; print(sync_tables(['daily_snapshot_audit','data_source_run','data_quality_issue']))"
```

回测具备全部窗口条件时，`/api/huijin/backtest` 应返回 `status=ok`、`is_backtest_ready=true`，并且 5/10/20/60 日窗口都至少有 `min_events` 个可评估事件。若只有部分窗口达标，接口返回 `partial_backtest_ready=true`，并在 `ready_windows` / `insufficient_windows` 标出达标和不足窗口；页面必须显示“样本不足/仅可观察”。

截至 2026-07-06 的当前本地数据，在严格使用 `disclosure_date <= 信号日` 后，5/10/20 日窗口已具备最小复盘样本，60 日窗口样本仍不足，原因是 2026-03-31 披露后的完整 60 个交易日评估路径尚少。不得把 2025-12-31 报告期日期当成披露日来扩大样本。

## 剩余质量状态解释

- `SOURCE_DATE_INFERRED`: 深市当前份额源日期由交易日历推断，保留 warning。
- `SSE_SOURCE_STALE`: 沪市份额源晚于交易日收盘后才可取，观察日早于最新源日时保留 warning。
- `CURRENT_SHARES_BELOW_CONFIG_HOLDING`: 当前 ETF 总份额低于披露 H0，仅提示必须回到 S0/A 和后续份额变化核验，不代表真实账户操作。
- `MISSING_H0` / `MISSING_VERIFIED_BASELINE`: 缺基金年报原文 H0 时必须 blocked。不得用联接基金、机构汇总或推测值替代。
