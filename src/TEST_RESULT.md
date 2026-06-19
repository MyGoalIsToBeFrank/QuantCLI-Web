# 后端模块自测报告

生成时间: 2026-06-19

## 1. 环境与模块加载

- Python 版本：3.14.5
- 虚拟环境：`.venv/`
- 核心依赖：`pandas`, `numpy`, `scikit-learn`, `Flask`, `yfinance`, `colorama`
- 所有 `src/` 下模块导入无报错。

## 2. 股票注册表

已注册 8 只股票：

| 代码 | 名称 | 市场 | 行业 |
|------|------|------|------|
| 002156.SZ | 通富微电 | A股 | 半导体封装 |
| 601225.SS | 陕西煤业 | A股 | 煤炭开采 |
| 300308.SZ | 中际旭创 | A股 | 半导体光模块 |
| 600460.SH | 士兰微 | A股 | 半导体 IDM |
| 605358.SH | 立昂微 | A股 | 半导体硅片 |
| 000725.SZ | 京东方A | A股 | 显示面板 |
| 002185.SZ | 华天科技 | A股 | 半导体封测 |
| AMD | AMD | 美股 | 半导体设计 |

## 3. Pipeline、Strategy、Model 注册表

已注册 Pipeline：`ma_dual`、`dt_logistic`、`rf_ma_dual`、`macd`、`rsi`、`boll`

已注册 Strategy：`prob_position`、`low_risk`、`macd_cross`、`rsi_threshold`、`boll_reversion`

已注册 Model：`dual_logistic`、`logistic`、`dual_random_forest`、`random_forest`、`macd_rule`、`rsi_rule`、`boll_rule`

## 4. 数据加载

`src.data.data_manager.load_stock(symbol)` 可正确加载 `data/stocks/<symbol>.csv`，返回标准化 DataFrame：

```python
columns = ['date', 'open', 'high', 'low', 'close', 'volume']
```

## 5. 组合回测（ComboBacktester）

以 `002156.SZ` + `ma_dual` + `prob_position` 近半年为例：

| 指标 | 数值 |
|------|------|
| 区间 | 2025-12-18 ~ 2026-06-17 |
| 初始资金 | 100,000 元 |
| 总收益率 | +40.83% |
| 最大回撤 | -3.58% |
| 交易次数 | 48 |
| 胜率 | 33.33% |
| 夏普 | 3.233 |
| 最终资产 | 140,829.72 元 |

## 6. 季度策略分析（QuarterlyAnalyzer）

`analyze 002156.SZ --start 2025-01-01 --end 2025-06-30 --max-drawdown 5`：

- 按季度滚动分析所有 (Pipeline × Strategy) 组合。
- 自动筛选最大回撤 < 5% 的组合。
- 输出每季度最佳组合与综合排名。

## 7. 全区间扫描（combo_scanner）

`scan 002156.SZ --start 2025-12-18 --end 2026-06-17 --max-drawdown 5 --save`：

- 在满足回撤约束的组合中选出收益最高者。
- 结果保存到 `data/best_combos.json`。

## 8. 今日决策（decide_stock）

`decide 002156.SZ --capital 100000 --fee 5 --lot 100`：

- 使用 `data/best_combos.json` 中的最佳组合。
- 返回开盘价、开盘跳空、预测信号、目标仓位、操作建议。

## 9. 批量报告（batch_report）

`strategy batch_report --symbols 002156.SZ,AMD --start 2025-01-01 --end 2025-06-30 --max-drawdown 5`：

- 输出分析结果表、回测结果表、今日决策表。
- 支持保存最佳组合。

## 10. 基本面记录

`fundamental list`：

- 正确加载 `data/fundamental_records.json`。
- 显示所有股票的分析状态、上次分析日期、建议下次日期。

## 11. 终端 K 线

`chart 002156.SZ --bars 20 --ma 5,20 --height 12`：

- 正确绘制 ASCII K 线、均线、成交量。
- 支持日期区间、美股颜色等选项。

## 12. Web API

Flask 测试客户端验证以下接口返回 200 且 `success=True`：

`/api/stocks`、`/api/pipelines`、`/api/strategies`、`/api/stock_data`、`/api/backtest`、`/api/decide_stock`、`/api/analyze`、`/api/best_combo`、`/api/fundamental_records`

## 13. 结论

当前后端核心流程（数据加载、Pipeline/Strategy/Model 注册、组合回测、季度分析、全区间扫描、今日决策、批量报告、基本面记录、终端 K 线、Web API）均运行无报错。
