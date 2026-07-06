# 汇金 ETF 份额观察当前遗留清单

> 更新时间: 2026-07-06
> 基线文档: `docs/huijin-watch-requirements.md`
> 使用说明: `docs/huijin-watch-usage.md`

## 已闭环

- audit 与 overview 已打通，NON_TRADING_DATE、SOURCE_DATE_INFERRED、SHARE_GAP、ABNORMAL_JUMP、MISSING_H0、MISSING_VERIFIED_BASELINE 可进入页面质量状态。
- blocked 样本不输出区间、不输出有效信号、不进入默认回测。
- 10x 份额扩张信号已定义基准量、连续天数、未触发原因，并与增强观察/减弱观察/观望区分。
- ETF 池已展示组内贡献拆解，并标注 blocked/warning 成分。
- 期指辅助已展示日期、合约覆盖和滞后状态，只作辅助验证，不进入核心公式。
- `/api/huijin/backtest` 已实现事件研究框架，使用 `disclosure_date <= 信号日`，T+1 或后续交易日评估，支持 5/10/20/60 日窗口。

## 当前仍存在的问题

- `588000` 缺直接可核验 H0，保持 `MISSING_H0` / `MISSING_VERIFIED_BASELINE` blocked；不得用联接基金、其他机构或推测值替代。
- 14 只样本目前多为 `verified_minimal`：具备 S0/H0/A 与 2026-03-31 披露日，可用于最小观察/事件研究；但仍需补公告 URL、文档 hash、页码/章节、逐主体持有人行，才能达到完整原文核验。
- 当前日期 2026-07-06 下，严格按 2026-03-31 披露日过滤后，5/10/20 日窗口具备最小复盘样本，60 日窗口样本不足；页面和接口必须显示“样本不足/仅可观察”，并列出不足窗口。
- 深市 `SOURCE_DATE_INFERRED` 属于源日期推断 warning；沪市 `SSE_SOURCE_STALE` 属于交易所源滞后 warning；二者不阻断公式，但默认不进入回测。
- CFFEX 最新数据可能滞后于观察日，仅影响辅助验证，不影响核心公式。

## 后续补强顺序

1. 为 `verified_minimal` 样本逐只补基金定报原文 URL/hash/页码/逐主体持有人行。
2. 人工复核 `588000` 是否存在直接中央汇金 H0；无法确认时继续 blocked。
3. 当披露日后可评估历史增长到足够长度，复查 60 日窗口是否达到 `min_events`。
4. 定期运行交易所份额采集、审计修复和读库同步，保持 `daily_snapshot_audit` 与 `data_quality_issue` 新鲜。
