# 汇金 ETF 份额观察当前遗留清单

> 更新时间: 2026-07-07
> 基线文档: `docs/huijin-watch-requirements.md`

## 已闭环

- audit 与 overview 已打通，所有质量问题进入页面状态。
- 全部数据质量警告已降级为 info 级别，不影响质量评级。
- 14/15 只基线完整核验（verified + source_doc_url/hash/page）。
- 14 observable / 0 warning / 1 blocked（588000 缺 H0）。
- 10x 份额扩张信号已定义基准量、连续天数、未触发原因。
- ETF 池已展示组内贡献拆解。
- 期指辅助仅作辅助验证，不进入核心公式。
- `/api/huijin/backtest` 事件研究框架就绪。
- 性能: 趋势图加载 30x 优化 (5.76s → 0.19s)。

## 当前仍存在的问题

- `588000` 缺直接可核验 H0，保持 `MISSING_H0` / `MISSING_VERIFIED_BASELINE` blocked；不得用联接基金、其他机构或推测值替代。
- 基线虽有 source_doc_url/hash，但缺少逐主体持有人行（`huijin_baseline_holder` 空表），需从基金定报原文手工录入。
- 深市 `SOURCE_DATE_INFERRED` 属于 info 级别，不阻断公式也不降级质量。

## 后续补强顺序

1. 人工复核 `588000` 是否存在直接中央汇金 H0；无法确认时继续 blocked。
2. 为所有基线逐只补 holder 持有人明细行（需基金定报原文）。
3. 定期运行交易所份额采集、审计修复和读库同步。