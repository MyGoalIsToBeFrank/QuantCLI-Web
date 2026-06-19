# 组合风险决策系统

> 在单股 Pipeline/Strategy/Backtest 之上，新增**组合层**（`src/portfolio/`）：
> 使用真实现金/持仓，对所有注册股票联合评估，偏好**低回撤、少回撤次数**而非最高收益，
> 固定 `lot_size=100`，并支持盘后 / 开盘实时 / 尾盘三种决策模式。
>
> 所有既有单股 `decide`/`backtest`/`scan`/WebUI 行为保持不变；组合层只**消费**下层能力。

---

## 1. 模块结构

```
src/portfolio/
├── schema.py            # 常量与决策模式（lot_size、DecisionMode）
├── state.py             # PortfolioState / Position / PortfolioStateManager
├── risk.py              # 回撤事件、风险评分、RiskProfile
├── quotes.py            # QuoteSnapshot 与行情提供者
├── modes.py             # 按模式构造决策数据帧
├── decision_engine.py   # 组合级今日决策编排
├── backtester.py        # 多股票联合回测器
└── reports.py           # CLI/API/WebUI 友好的格式化
```

数据文件：

```
data/portfolio_state.json          # 账户状态（人类可编辑）
data/portfolio_risk_profile.json   # 风险配置
```

---

## 2. 账户状态 schema

`data/portfolio_state.json`：

```json
{
  "schema_version": 1,
  "updated_at": "2026-06-19T15:00:00+08:00",
  "cash": 100000.0,
  "lot_size": 100,
  "positions": {
    "002156.SZ": { "shares": 800, "avg_cost": 62.5, "note": "manual" }
  }
}
```

规则：

- `lot_size` 默认 `100`，并作为执行单位；买卖建议向下取整到 100 股的整数倍。
- `shares` 为非负整数，`cash` 非负。
- 未在 `stock_registry` 注册的股票被拒绝。
- 文件缺失时创建默认空状态（`cash=100000.0, positions={}, lot_size=100`）。

---

## 3. 风险配置 schema

`data/portfolio_risk_profile.json`（默认值刻意保守）：

| 字段 | 默认 | 含义 |
|------|------|------|
| `max_total_position` | 0.40 | 组合最大股票总仓位 |
| `max_single_position` | 0.10 | 单只股票最大仓位 |
| `max_late_session_position` | 0.20 | 尾盘新建仓总敞口上限 |
| `min_cash_ratio` | 0.20 | 交易后最低现金比例 |
| `drawdown_limit_pct` | 5.0 | 组合权益回撤参考线（评分归一化/未来组合级守护） |
| `drawdown_event_threshold_pct` | 3.0 | 触发"一次回撤事件"的阈值 |
| `max_drawdown_events` | 3 | 允许的最大回撤事件数（超出则硬性拒绝） |
| `late_session_take_profit_pct` | 2.0 | 尾盘策略次日止盈目标 |
| `late_session_exit` | next_day_tail_if_not_hit | 未达标时的兜底离场 |
| `risk_lookback_days` | 120 | 风险度量回看窗口（交易日） |
| `single_drawdown_limit_pct` | 25.0 | 单股近窗口价格最大回撤硬性上限 |

> **为何区分 `drawdown_limit_pct` 与 `single_drawdown_limit_pct`？**
> 5% 面向**组合权益**回撤控制；而单只**个股价格**回撤天然更大（几十个百分点很常见）。
> 若用 5% 去硬性卡个股价格回撤，会拒绝几乎所有标的。因此个股硬性阈值单列、更现实。

---

## 4. 决策模式与数据可用性（最重要的不变量）

| 模式 | 用例 | 允许的数据 | 额外输出 |
|------|------|-----------|---------|
| `close_after_market` | 盘后、下一笔在次日开盘 | 完整日线 | 无 |
| `open_realtime` | 已知 T 开盘价 | 完整 T-1 日线 + T 开盘价（T 收/高/低被遮蔽为开盘价，量=0） | 同日目标调整 |
| `late_session` | 临近收盘的尾盘选股 | 仅提供的行情快照字段（开/高/低/现价/量/前收/时间戳/来源） | 候选买入 + 次日 +2% 止盈计划 |

**禁止为改善回测结果而违反该不变量。**

`open_realtime` 复用既有 `build_latest_open_decision_frame`，延续"无前视"纪律。

---

## 5. 决策流程

1. 读取 `PortfolioState` 与 `RiskProfile`。
2. 逐只注册股票：加载数据 → 解析最佳组合（`best_combos.json`，否则默认组合）→ 构造模式数据帧 →
   pipeline 预测 → strategy 在**真实持仓上下文**下决策 → 计算风险度量。
3. **风险优先排序**（先过滤再打分）：
   ```
   risk_score        = 0.45*回撤 + 0.25*回撤事件 + 0.15*波动 + 0.15*流动性惩罚
   opportunity_score = 0.60*预测强度 + 0.25*趋势确认 + 0.15*流动性
   final_rank        = opportunity_score - risk_score   # 越大越优先
   ```
   所有分量都会暴露，便于解释"为什么入选/被拒"。
4. **分配**：在 `max_total_position` / `max_single_position` / `min_cash_ratio`
   （尾盘还有 `max_late_session_position`）约束下，先卖后买，按手取整，复用下层成交逻辑。
5. 尾盘模式额外生成次日 `+2%` 止盈与兜底离场计划。

系统只产出**建议**，不自动下单。

---

## 6. CLI 用法

```bash
QuantCLI.bat portfolio show
QuantCLI.bat portfolio set-cash 100000
QuantCLI.bat portfolio set-position 002156.SZ 800 --avg-cost 62.5
QuantCLI.bat portfolio remove-position 002156.SZ
QuantCLI.bat portfolio risk-profile
QuantCLI.bat portfolio risk-profile set --max-total-position 0.40 --max-single-position 0.10

# 组合级今日决策
QuantCLI.bat portfolio decide --mode close_after_market
QuantCLI.bat portfolio decide --mode open_realtime --open 002156.SZ=68.27
QuantCLI.bat portfolio decide --mode late_session --quote quotes.json

# 多股票联合回测（一笔总资金，受组合风险约束）
QuantCLI.bat portfolio backtest --start 2026-01-01 --end 2026-06-19 --capital 100000
```

`quotes.json`（尾盘模式）示例：

```json
{
  "002156.SZ": {
    "price": 68.27, "open": 66.99, "high": 69.35, "low": 66.39,
    "prev_close": 67.22, "volume": 163341799,
    "timestamp": "2026-06-19T14:50:00+08:00", "source": "manual"
  }
}
```

---

## 7. API

```
GET    /api/portfolio_state
PUT    /api/portfolio_state
POST   /api/portfolio_position
DELETE /api/portfolio_position
GET    /api/portfolio_risk_profile
PUT    /api/portfolio_risk_profile
POST   /api/portfolio_decide      # body: {mode, symbols?, quotes?, open_prices?}
```

既有 `/api/decide_stock`、`/api/backtest` 等保持不变。

---

## 8. WebUI

顶部导航新增「💼 组合决策」标签，包含：组合状态编辑、风险配置编辑、决策模式选择
（open/late 模式按需录入行情 JSON）、决策结果（订单建议 / 选中与拒绝候选 / 评分分量 /
尾盘离场计划），并显著标注"建议非委托"的安全横幅。

---

## 9. 多股票联合回测

`PortfolioBacktester`：一笔总资金在多只股票间联合分配。

- **成交价可配置 `execution_price ∈ {close, open}`，默认 `close`（更现实）**：
  `close` 在当日收盘观察后按收盘价成交（用截至当日的完整 bar 决策，无前视）；
  `open` 复现旧的 T 开盘价语义。CLI：`--exec-price`。
- 每日：逐股预测 → 风险优先排序 → 组合约束下分配 → 按成交价成交 → 收盘市值入账。
- 每标的每日 ≤1 笔、卖出只动用历史持仓，故 **A 股 T+1 在日线级天然满足**（日内级需显式锁仓，见 handover §14.5）。
- 默认纳入交易日历一致的标的（A 股）；跨市场标的（如美股）需显式传入并以日期交集对齐。
- 输出：合并权益曲线、收益、**最大回撤**、**回撤次数(>3% / >5%)**、平均/峰值敞口、交易记录。

### Walk-forward 样本外组合选择（无前视调参）

默认回测用 `best_combos.json`（在重叠区间选出，含选择性前视，**不是诚实基准**）。
加 `--walk-forward` 改为**滚动样本外**选组合：在每个再平衡点只用更早的数据选组合，前向区间对其样本外。

```bash
QuantCLI.bat portfolio backtest --start 2026-01-01 --end 2026-06-19 \
    --capital 100000 --walk-forward --wf-train-days 180 --wf-step-days 63
```

实现：`src/portfolio/walkforward.py` 的 `WalkForwardSelector`（训练窗口严格早于再平衡点），
回测 `PortfolioBacktester(combo_plan=...)` 按日切换生效组合。**调参/选组合不得前视**——
公平比较组合 vs 单股 vs 买入持有，必须在同一套 walk-forward 协议下进行（详见 handover §15）。

> 回撤次数定义：权益自峰值跌破 `-阈值%` 记为一次事件，回升至距峰值 1% 以内或创新高即结束；
> 该定义在 `tests/test_portfolio_risk.py` 中被固化测试。

---

## 10. 限制（V1）

- 不接券商下单、不做自动实时行情流、不支持融资融券/做空/税务/多账户。
- 尾盘依赖手动行情快照；`YFinanceIntradayProvider` 可在同一 `QuoteProvider` 接口下后续补充。
- 联合回测为日线级别，不做分钟级尾盘模拟（V2）。
