# Portfolio Risk Decision Handover Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` and `superpowers:test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portfolio-level risk-control decision system that uses current cash/positions, keeps `lot_size=100`, evaluates all registered stocks, favors low drawdown and fewer drawdown events over highest return, and can host close-after-market, open-realtime, and late-session strategies while preserving all existing single-stock CLI/WebUI/API behavior.

**Architecture:** Add a new `src/portfolio/` subsystem above the existing pipeline/strategy/backtest layers. Existing single-stock pipelines continue to produce predictions; the new portfolio layer loads account state, gathers mode-specific market snapshots, scores all registered symbols with risk-first rules, allocates target positions under portfolio constraints, and emits actionable order suggestions plus optional late-session exit plans.

**Tech Stack:** Python, pandas, Flask, existing CLI command framework, existing frontend static JS/CSS/HTML, JSON state files under `data/`, yfinance/manual quote input for initial intraday support.

---

## 实施状态（2026-06-19 更新）

### ✅ Phase 1 — 组合风险决策：已完成

第 10 节的全部任务（Task 1–8）均已实现并通过测试（**67 个测试全绿**，含后端自测、`py_compile`、`node --check`、浏览器 WebUI 验证）。落地内容：

- `src/portfolio/` 全部模块：`schema / state / risk / quotes / modes / decision_engine / reports`。
- CLI `portfolio show / set-cash / set-position / remove-position / risk-profile / decide`，`scripts/portfolio.bat`。
- API 七个 `/api/portfolio_*` 端点；既有端点零改动。
- WebUI「💼 组合决策」标签 + 一轮整体美化（按钮语义层、安全横幅、买卖标签、分块小标题等）。
- 文档 `docs/portfolio_decision.md`，更新 README。

**相对原计划的偏差（均为有意为之）：**

1. **新增多股票联合回测器** `src/portfolio/backtester.py` + CLI `portfolio backtest`。原计划把组合级回测列为 V2，但用户要求"100000 为总本金、多股票联合策略"的回测，故提前实现日线级联合回测。
2. **风险语义修正**：原"历史最大回撤 vs 5%"会拒绝所有标的。改为**近窗口**度量（`risk_lookback_days`，默认 120 日），并拆分两个回撤限：`drawdown_limit_pct`（组合权益，评分用）与新增 `single_drawdown_limit_pct`（个股价格硬限，默认 25%）。
3. 未改 `src/backtest/metrics.py`；回撤事件等度量放在 `src/portfolio/risk.py`。
4. 修复 `src/cli/main.py` 在 import 期重包装 `sys.stdout` 与 colorama 在非 TTY 下包装捕获缓冲区导致的 pytest `I/O operation on closed file`（加 `isatty()` 守卫）。

### ⏳ Phase 2 — 日内回测层：待实施（详见第 14 节）

**范围澄清（用户确认）：本阶段只做"回测层面"，真实/实时执行是另一回事，不在本阶段。**

已知反馈，已并入 Phase 2 设计：

- **开盘价成交不现实，收盘价更现实** → 回测成交价改为可配置，默认按 **bar 收盘价** 成交。
- **支持"一日内何时卖出"的决策** → 引入日内（5m）卖出择时回测。
- **批量获取日内数据**（已实测可行，见第 14.2 节数据探测结论）。
- **数据量过大就用 5min 决策窗口** → 默认 5m（数据量其实很小，瓶颈是 yfinance 回溯窗口，需增量落盘缓存）。
- **模型不必每次决策都训练** → `fit` 一次、`predict` 每个 bar 复用（拟合模型缓存）。
- **日内决策也是一种"需要注册的资产"** → 新增可注册的"时间粒度（Timeframe）"与"日内卖出策略"注册表。

---

## 1. Motivation And Current-State Diagnosis

The platform currently has a reliable single-stock research loop:

- data loading from `data/stocks/*.csv`
- registered pipeline/model/strategy system
- single-combo backtesting
- scan/analyze to find a best combo per stock
- `decide` for one or more symbols
- WebUI dashboard, backtest, decision, batch report

The missing layer is portfolio state and portfolio risk control. Current `decide` assumes `cash=capital`, `shares=0`, and `current_position=0.0`. That is fine for a single-stock what-if decision, but it is not enough for real portfolio operation where:

- some cash is already invested
- holdings have different sizes and costs
- a decision should consider all registered stocks together
- total exposure, single-stock exposure, and late-session exposure must be capped
- the system should prefer controlled drawdown and fewer drawdown events, not highest historical return
- `lot_size=100` must remain the execution unit

The user's cited tail-session idea is valuable but should not become a separate system. It should be implemented as one decision mode inside the portfolio framework. The portfolio layer should be able to decide:

- after close, before next open: use only complete daily bars
- after T-day open: use known T-day open without peeking at T-day close/high/low
- near T-day close: use intraday/tail-session snapshot when available, then produce a late-session buy and next-day exit plan

This keeps the architecture honest: market timing determines what data is legally available, while portfolio risk controls determine how much capital can be allocated.

---

## 2. Core Product Decisions

### 2.1 V1 Scope

V1 should implement **portfolio risk decision** first, while designing the mode interface so late-session strategy is supported.

V1 includes:

- account state stored locally as JSON
- editable cash and positions in CLI and WebUI
- portfolio-level decision across all registered stocks
- fixed `lot_size=100`
- ranking by low drawdown, low drawdown-event count, positive signal, and liquidity proxy
- three decision modes in the public interface:
  - `close_after_market`
  - `open_realtime`
  - `late_session`
- late-session mode can work with manual quote snapshots first
- yfinance intraday support can be added behind the same quote-provider interface

V1 does not include:

- broker API order placement
- automatic live streaming
- margin/shorting
- tax accounting
- multi-account support
- high-frequency intraday backtest

### 2.2 Tail-Session Strategy Positioning

Late-session strategy is an execution style, not the whole system.

Its V1 rule should be conservative:

- only use candidates already passing portfolio risk filters
- total late-session exposure capped, default `20%`
- single-symbol late-session exposure capped, default `10%`
- buy near tail session only when a mode-specific signal is positive
- next-day target exit: `+2%` limit target
- next-day fallback exit: sell near next-day close if target was not reached
- optional protective stop for V2, not forced in V1 unless configured

Late-session requires finer data than daily bars. The architecture must accept this, but implementation should start with a minimal `QuoteSnapshot` input so the rest of the system can be built before fully automating minute data.

---

## 3. Proposed Architecture

### 3.1 New Package Layout

Create a new package:

```text
src/portfolio/
├── __init__.py
├── state.py              # PortfolioState, Position, load/save/update JSON state
├── schema.py             # dataclasses/constants shared by state/decision/API
├── quotes.py             # QuoteSnapshot, quote providers, manual/yfinance hooks
├── modes.py              # mode-specific frame/snapshot builders
├── risk.py               # drawdown events, risk score, allocation constraints
├── decision_engine.py    # portfolio-wide decision orchestration
└── reports.py            # CLI/API/WebUI-friendly formatting helpers
```

Add tests:

```text
tests/test_portfolio_state.py
tests/test_portfolio_risk.py
tests/test_portfolio_decision_engine.py
tests/test_portfolio_modes.py
tests/test_portfolio_cli_api.py
```

Add default data files:

```text
data/portfolio_state.json
data/portfolio_risk_profile.json
```

The existing `src/strategy.py`, `src/backtest/`, `src/cli/commands/decide_cmd.py`, and `/api/decide_stock` remain. The new portfolio system consumes their lower-level capabilities instead of replacing them.

### 3.2 Portfolio State Schema

`data/portfolio_state.json` should be human-editable and safe to load.

Required schema:

```json
{
  "schema_version": 1,
  "updated_at": "2026-06-19T15:00:00+08:00",
  "cash": 100000.0,
  "lot_size": 100,
  "positions": {
    "002156.SZ": {
      "shares": 800,
      "avg_cost": 62.5,
      "note": "manual"
    }
  }
}
```

Rules:

- `lot_size` defaults to `100` and remains the execution unit.
- shares must be non-negative integers.
- for A-share execution, buy/sell suggestions round down to lots of 100.
- cash must be non-negative.
- unknown symbols are rejected unless explicitly allowed by a future migration.
- missing state file creates a default empty state with `cash=100000.0`, `positions={}`, `lot_size=100`.

### 3.3 Risk Profile Schema

`data/portfolio_risk_profile.json` defines default risk controls:

```json
{
  "schema_version": 1,
  "max_total_position": 0.40,
  "max_single_position": 0.10,
  "max_late_session_position": 0.20,
  "min_cash_ratio": 0.20,
  "drawdown_limit_pct": 5.0,
  "drawdown_event_threshold_pct": 3.0,
  "max_drawdown_events": 3,
  "rebalance_threshold": 0.05,
  "late_session_take_profit_pct": 2.0,
  "late_session_exit": "next_day_tail_if_not_hit"
}
```

Defaults are intentionally conservative. The objective is not maximum historical return. It is controlled exposure with fewer drawdown events.

### 3.4 Decision Modes

#### `close_after_market`

Use case:

- market is closed
- T-day full daily bar is available
- next trade will normally happen next open

Data allowed:

- complete historical daily bars up to latest local date
- no next-day open
- no future intraday price

Output:

- target portfolio allocation for next session
- no late-session exit plan

#### `open_realtime`

Use case:

- T-day open price is known
- T-day close/high/low/volume are not known

Data allowed:

- all completed daily bars up to T-1
- T-day open price
- T-day row masked as open-only:
  - `open = known open`
  - `high = open`
  - `low = open`
  - `close = open`
  - `volume = 0`

Output:

- same-day target adjustment based on current portfolio state

This continues the no-front-look discipline already introduced in `build_latest_open_decision_frame`.

#### `late_session`

Use case:

- near end of trading day
- most of T-day shape is known
- user wants tail-session candidate selection

Data required:

- latest price
- day open/high/low/current volume
- previous close
- timestamp
- data source label

V1 can accept manual quote snapshots from CLI/WebUI. V2 can automate yfinance intraday or another data source.

Output:

- candidate buy list
- target allocation under late-session exposure cap
- suggested buy shares
- planned next-day `+2%` take-profit price
- fallback exit rule

### 3.5 Quote Snapshot Schema

Use one internal dataclass and JSON-compatible shape:

```json
{
  "symbol": "002156.SZ",
  "timestamp": "2026-06-19T14:50:00+08:00",
  "price": 68.27,
  "open": 66.99,
  "high": 69.35,
  "low": 66.39,
  "volume": 163341799,
  "prev_close": 67.22,
  "source": "manual",
  "granularity": "tail"
}
```

For V1, `manual` is enough. A `YFinanceIntradayProvider` can be implemented later behind the same interface.

---

## 4. Portfolio Decision Flow

### 4.1 Input

The decision engine receives:

- `PortfolioState`
- `RiskProfile`
- list of registered symbols
- decision mode
- optional quote snapshots
- optional restricted pipeline/strategy list
- fee and lot size

### 4.2 Per-Symbol Evaluation

For each registered stock:

1. Load local data.
2. Resolve best combo:
   - use `data/best_combos.json` when available
   - fallback to configured default combo if no best combo exists
   - optional scan is not run automatically in V1 because it is slow
3. Build mode-specific decision frame:
   - close mode: raw completed bars
   - open mode: append/mask open-only row
   - late mode: append/mask quote snapshot row
4. Run pipeline prediction.
5. Run strategy decision with actual current position context.
6. Collect risk metrics:
   - historical max drawdown
   - drawdown event count
   - recent volatility
   - trade count
   - data freshness
   - liquidity proxy from volume/turnover if available
7. Produce a `CandidateDecision`.

### 4.3 Risk-First Candidate Ranking

Do not sort by highest return first.

Recommended ranking:

1. Reject if data stale or invalid.
2. Reject if historical max drawdown breaches hard limit, unless already held and sell/trim is being evaluated.
3. Reject if drawdown event count exceeds profile limit.
4. Prefer candidates with positive or neutral-positive signal.
5. Prefer lower drawdown.
6. Prefer fewer drawdown events.
7. Prefer adequate liquidity.
8. Use expected/probability score only after risk filters.

Suggested score:

```text
risk_score =
  0.45 * normalized_max_drawdown
+ 0.25 * normalized_drawdown_events
+ 0.15 * normalized_recent_volatility
+ 0.15 * data_or_liquidity_penalty

opportunity_score =
  0.60 * normalized_prediction_strength
+ 0.25 * trend_confirmation
+ 0.15 * liquidity_score

final_rank =
  opportunity_score - risk_score
```

The implementation should expose the score components so the user can understand why a stock is selected or rejected.

### 4.4 Allocation

The allocator converts candidate target weights to orders.

Constraints:

- total stock exposure <= `max_total_position`
- single stock exposure <= `max_single_position`
- late-session total exposure <= `max_late_session_position`
- cash after proposed trades >= `min_cash_ratio * total_equity`
- buy and sell shares rounded by `lot_size=100`
- existing holdings are considered before new buys
- sell/trim suggestions can be emitted when current position exceeds risk cap

Order calculation should use existing `calculate_trade_shares()` for final lot rounding.

### 4.5 Output Shape

Portfolio decision result:

```json
{
  "mode": "open_realtime",
  "timestamp": "2026-06-19T09:35:00+08:00",
  "portfolio": {
    "cash": 100000.0,
    "estimated_equity": 150000.0,
    "current_stock_exposure": 0.30,
    "target_stock_exposure": 0.38
  },
  "risk_profile": {
    "max_total_position": 0.4,
    "max_single_position": 0.1,
    "lot_size": 100
  },
  "orders": [
    {
      "symbol": "002156.SZ",
      "action": "buy",
      "shares": 300,
      "price": 68.27,
      "estimated_cash_change": -20486.0,
      "target_position": 0.10,
      "reason": "positive signal, drawdown within limit, portfolio cap available"
    }
  ],
  "candidates": [
    {
      "symbol": "002156.SZ",
      "pipeline": "dt_logistic",
      "strategy": "prob_position",
      "prediction": {"prob_bull": 0.62, "signal": "bull"},
      "risk": {
        "max_drawdown_pct": -4.61,
        "drawdown_events": 2,
        "risk_score": 0.22
      },
      "rank": 1,
      "selected": true
    }
  ],
  "late_session_plan": [
    {
      "symbol": "002156.SZ",
      "entry_price": 68.27,
      "take_profit_price": 69.64,
      "fallback_exit": "next_day_tail_if_not_hit"
    }
  ]
}
```

---

## 5. CLI Design

Add a new top-level command group:

```text
QuantCLI.bat portfolio ...
```

Subcommands:

```text
QuantCLI.bat portfolio show
QuantCLI.bat portfolio set-cash 100000
QuantCLI.bat portfolio set-position 002156.SZ 800 --avg-cost 62.5
QuantCLI.bat portfolio remove-position 002156.SZ
QuantCLI.bat portfolio decide --mode open_realtime --open 002156.SZ=68.27
QuantCLI.bat portfolio decide --mode close_after_market
QuantCLI.bat portfolio decide --mode late_session --quote quotes.json
QuantCLI.bat portfolio risk-profile
QuantCLI.bat portfolio risk-profile set --max-total-position 0.40 --max-single-position 0.10
```

Behavior:

- `portfolio show` prints cash, positions, estimated exposure, and latest known prices.
- `set-position` does not validate against broker state; it updates local state.
- `decide` evaluates all registered active stocks.
- `--symbols` optionally restricts the universe.
- `--mode auto` can be added after V1; explicit mode is clearer initially.
- output includes order table, rejected candidates, score components, and late-session exit plan.

Existing commands remain:

- `decide` remains single-stock.
- `scan` remains research/backtest.
- `backtest` remains single-combo.
- `data verify` remains data validation.

---

## 6. WebUI Design

Add a new view/tab:

```text
组合决策
```

Sections:

1. **Portfolio State**
   - cash input
   - positions grid
   - add/update/remove position
   - `lot_size=100` shown as locked default

2. **Risk Profile**
   - max total stock exposure
   - max single stock exposure
   - max late-session exposure
   - min cash ratio
   - max drawdown limit
   - max drawdown event count

3. **Decision Mode**
   - close after market
   - open realtime
   - late session
   - quote inputs appear depending on mode

4. **Decision Output**
   - order suggestions
   - selected candidates
   - rejected candidates
   - score breakdown
   - cash after proposed trades
   - exposure after proposed trades
   - late-session next-day exit plan

5. **Safety Banner**
   - explicitly show that these are decision suggestions, not broker orders
   - show data timestamp/source

WebUI should not force full-screen dashboard redesign. It should reuse existing tab/navigation style.

---

## 7. API Design

Add endpoints:

```http
GET  /api/portfolio_state
PUT  /api/portfolio_state
POST /api/portfolio_position
DELETE /api/portfolio_position
GET  /api/portfolio_risk_profile
PUT  /api/portfolio_risk_profile
POST /api/portfolio_decide
```

Request for `/api/portfolio_decide`:

```json
{
  "mode": "open_realtime",
  "symbols": ["002156.SZ", "300308.SZ"],
  "quotes": {
    "002156.SZ": {
      "price": 68.27,
      "open": 66.99,
      "high": 69.35,
      "low": 66.39,
      "volume": 163341799,
      "prev_close": 67.22,
      "timestamp": "2026-06-19T09:35:00+08:00",
      "source": "manual"
    }
  }
}
```

Response follows the output shape in Section 4.5.

Compatibility:

- Do not change `/api/decide_stock`.
- Do not change `/api/backtest`.
- Existing WebUI calls must continue to work.

---

## 8. Backtesting And Metrics Design

V1 should not attempt a full minute-level portfolio backtest.

V1 should add reusable risk metrics:

- max drawdown
- drawdown event count
- recent volatility
- exposure history helper

Drawdown event definition:

- A drawdown event starts when equity drawdown crosses below `-drawdown_event_threshold_pct`.
- It ends when equity recovers to within `1%` of prior peak or a new peak is reached.
- Count events over the backtest window.

This definition must be tested because “回撤次数” can otherwise be interpreted ambiguously.

V2 can add:

- portfolio-level multi-stock backtester
- tail-session strategy simulator
- next-day take-profit/fallback-exit simulation

---

## 9. Data Plan For Late Session

### V1

Use manual quote snapshots through CLI/WebUI/API.

This is enough to validate:

- data shape
- decision-mode interface
- risk allocation
- late-session exit plan

### V2

Add provider abstraction:

```python
class QuoteProvider:
    def get_snapshot(self, symbol: str) -> QuoteSnapshot:
        ...
```

Implement:

- `ManualQuoteProvider`
- `YFinanceQuoteProvider`
- optional cached provider under `data/intraday_cache/`

Data validation:

- snapshot timestamp must be present
- price/open/high/low must be positive
- `low <= price <= high`
- `prev_close > 0`
- stale snapshots are rejected or warned

---

## 10. Implementation Plan

### Task 1: Portfolio Schemas And State

**Files:**

- Create: `src/portfolio/__init__.py`
- Create: `src/portfolio/schema.py`
- Create: `src/portfolio/state.py`
- Create: `tests/test_portfolio_state.py`

- [x] Write failing tests for default state creation.
- [x] Write failing tests for saving and loading `data/portfolio_state.json`.
- [x] Write failing tests for invalid negative cash and invalid negative shares.
- [x] Implement `Position`, `PortfolioState`, `PortfolioStateManager`.
- [x] Ensure default `lot_size=100`.
- [x] Run `pytest tests/test_portfolio_state.py -q`.

### Task 2: Risk Profile And Drawdown Event Metrics

**Files:**

- Create: `src/portfolio/risk.py`
- Create: `tests/test_portfolio_risk.py`
- Modify: `src/backtest/metrics.py` only if shared helper belongs there after tests prove it.

- [x] Write failing test for drawdown event count with two events.
- [x] Write failing test for no event when drawdown stays above threshold.
- [x] Write failing test for risk profile load defaults.
- [x] Implement `count_drawdown_events()`.
- [x] Implement `RiskProfile`.
- [x] Implement risk score component calculation.
- [x] Run `pytest tests/test_portfolio_risk.py -q`.

### Task 3: Quote Snapshots And Decision Modes

**Files:**

- Create: `src/portfolio/quotes.py`
- Create: `src/portfolio/modes.py`
- Create: `tests/test_portfolio_modes.py`

- [x] Write failing test for `close_after_market` using complete bars only.
- [x] Write failing test for `open_realtime` masking current row to open-only.
- [x] Write failing test for `late_session` appending quote snapshot row.
- [x] Write failing test rejecting stale or invalid quote snapshots.
- [x] Implement `QuoteSnapshot`.
- [x] Implement mode builders.
- [x] Reuse existing `build_latest_open_decision_frame` where appropriate.
- [x] Run `pytest tests/test_portfolio_modes.py -q`.

### Task 4: Portfolio Decision Engine

**Files:**

- Create: `src/portfolio/decision_engine.py`
- Create: `src/portfolio/reports.py`
- Create: `tests/test_portfolio_decision_engine.py`

- [x] Write failing test that all registered symbols can be evaluated with a stub pipeline.
- [x] Write failing test that current holdings and cash affect trade suggestions.
- [x] Write failing test that single-symbol cap is enforced.
- [x] Write failing test that total exposure cap is enforced.
- [x] Write failing test that `lot_size=100` rounds orders down.
- [x] Write failing test that low drawdown beats higher return when risk profile demands it.
- [x] Implement `PortfolioDecisionEngine`.
- [x] Implement candidate ranking.
- [x] Implement allocation and order generation.
- [x] Implement late-session exit plan generation.
- [x] Run `pytest tests/test_portfolio_decision_engine.py -q`.

### Task 5: CLI Portfolio Commands

**Files:**

- Create: `src/cli/commands/portfolio_cmd.py`
- Modify: `src/cli/main.py`
- Modify: `src/cli/commands/__init__.py`
- Create: `tests/test_portfolio_cli_api.py`

- [x] Write failing import/registration test for `portfolio` command.
- [x] Write failing CLI test for `portfolio show`.
- [x] Write failing CLI test for `portfolio set-cash`.
- [x] Write failing CLI test for `portfolio set-position`.
- [x] Write failing CLI test for `portfolio decide --mode close_after_market`.
- [x] Implement command registration.
- [x] Implement CLI handlers.
- [x] Run `pytest tests/test_portfolio_cli_api.py -q`.
- [x] Run `cmd /c QuantCLI.bat portfolio show --no-pause`.

### Task 6: API Endpoints

**Files:**

- Modify: `src/api_server.py`
- Extend: `tests/test_portfolio_cli_api.py`

- [x] Write failing Flask client test for `GET /api/portfolio_state`.
- [x] Write failing Flask client test for `PUT /api/portfolio_state`.
- [x] Write failing Flask client test for `POST /api/portfolio_decide`.
- [x] Implement endpoints.
- [x] Ensure existing endpoints still pass.
- [x] Run targeted Flask tests.

### Task 7: WebUI Portfolio View

**Files:**

- Modify: `src/frontend/index.html`
- Modify: `src/frontend/js/api.js`
- Modify: `src/frontend/js/app.js`
- Modify: `src/frontend/css/style.css`

- [x] Add navigation tab “组合决策”.
- [x] Add portfolio state editor.
- [x] Add risk profile editor.
- [x] Add mode selector.
- [x] Add quote input table for open/late modes.
- [x] Add decision result table.
- [x] Show selected and rejected candidates separately.
- [x] Show late-session exit plan when present.
- [x] Run `node --check src/frontend/js/*.js`.
- [x] Start Flask and verify WebUI with Browser.

### Task 8: Documentation And Verification

**Files:**

- Create: `docs/portfolio_decision.md`
- Update: `README.md` only if it has a CLI/API section that should mention portfolio commands.

- [x] Document state file schema.
- [x] Document decision modes and data availability.
- [x] Document late-session strategy limitations.
- [x] Document CLI examples.
- [x] Run full test suite:
  - `.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider`
  - `.venv\Scripts\python.exe tests\test_backend.py`
  - `.venv\Scripts\python.exe -m py_compile <all src py files>`
  - `node --check src/frontend/js/api.js`
  - `node --check src/frontend/js/app.js`
  - `node --check src/frontend/js/kline.js`
  - `node --check src/frontend/js/config.js`

---

## 11. Acceptance Criteria

The implementation is acceptable only if:

- Existing single-stock `decide`, `backtest`, `scan`, and WebUI dashboard continue to work.
- New `portfolio show` displays cash, positions, and lot size.
- New `portfolio decide` evaluates all registered active stocks by default.
- Portfolio decision uses actual current cash and shares from state.
- Buy/sell recommendations are rounded by `lot_size=100`.
- Risk profile can cap total exposure and single-stock exposure.
- Candidate ranking exposes risk reasons, not just return rank.
- Drawdown event count is tested and visible in candidate details.
- `late_session` mode exists in CLI/API/WebUI and can emit a next-day 2% take-profit plan when quote snapshots are supplied.
- No broker orders are placed automatically.
- Full backend, CLI, API, and WebUI checks pass.

---

## 12. Key Risks And Mitigations

### Risk: Late-session data quality is weak

Mitigation:

- V1 uses manual quote snapshots.
- Snapshot source/timestamp is always shown.
- Stale or malformed snapshots are rejected.
- Automated intraday provider is added later behind the same interface.

### Risk: Portfolio scoring becomes overfit

Mitigation:

- Keep ranking explainable.
- Risk filters come before probability score.
- Do not add opaque factors unless they map to a clear market idea.
- Show score components in CLI/WebUI.

### Risk: User mistakes local holdings

Mitigation:

- State editor shows timestamp.
- CLI confirms changes.
- WebUI separates “saved state” from “decision output”.
- No automatic order execution.

### Risk: Existing features regress

Mitigation:

- New code lives under `src/portfolio/`.
- Existing endpoints are not renamed.
- Add tests for new endpoints without weakening existing tests.

---

## 13. Handover Notes For The Implementer

Start with state and risk metrics. Do not start with WebUI.

Recommended implementation order:

1. `PortfolioState`
2. `RiskProfile` and drawdown-event metrics
3. mode builders and quote snapshots
4. decision engine
5. CLI
6. API
7. WebUI
8. docs and full verification

Keep the first working version conservative. A mediocre but honest risk-controlled decision engine is better than a visually impressive strategy that hides risk.

The most important invariant is data availability by mode:

- close mode: complete bars only
- open mode: T open allowed, T close/high/low disallowed
- late mode: only supplied quote snapshot fields are allowed

Do not violate this invariant to improve backtest results.

---

## 14. Phase 2 — 日内回测层（详细计划）

> **范围：仅回测层。** 真实/实时下单、券商对接、实时行情流均不在本阶段。
> 本阶段目标：在历史 5 分钟（或 1 分钟）K 线上，**回测"日内何时卖出"的择时策略**，
> 并把不现实的开盘价成交改为更现实的**收盘价成交**。

### 14.1 动机与用户反馈映射

| 用户反馈 | Phase 2 中的落地点 |
|----------|--------------------|
| 开盘价成交不现实，收盘价更现实 | 14.6 可配置成交价，回测默认 `close` |
| 支持"一日内何时卖出"的决策 | 14.4 日内卖出择时策略 + 14.5 日内回测器 |
| 先尝试批量获取数据 | 14.2 数据探测结论 + 14.3 日内数据层（增量缓存） |
| 数据量大就 5min 窗口 | 默认 5m；数据量其实很小，瓶颈是回溯窗口 |
| 模型不必每次决策都训练 | 14.4 拟合模型缓存：`fit` 一次、`predict` 每 bar |
| 日内决策是"需要注册的资产" | 14.3 Timeframe 注册表 + 14.4 日内策略注册表 |

### 14.2 数据探测结论（2026-06-19 实测 yfinance）

实测 `yfinance.download(interval=..., period=...)`：

| 标的 | 粒度 | 可回溯 | 每日 bar 数 |
|------|------|--------|-------------|
| 002156.SZ（A股） | 5m | ~60 天（3893 行 / 59 日） | ~48–66 |
| 002156.SZ | 1m | ~7 天（1650 行 / 5 日） | ~240 |
| 002156.SZ | 60m | ~2 年（1450 行 / 242 日） | ~6 |
| AMD（美股） | 5m | ~60 天（4680 行 / 60 日） | ~78 |

结论：

1. **A 股与美股的日内数据都能拿到**，5m 最稳健（60 天窗口）。
2. **数据量不是瓶颈**：8 标的 × 60 日 × ~50 bar ≈ 2.4 万行，极小。
3. **真正的限制是 yfinance 回溯窗口**（1m≈7d、5m≈60d）与偶发失败（个别标的 5m 瞬时空）。
   → 必须**增量落盘缓存**，随时间累积更长的日内历史；并加重试/退避。
4. **默认粒度 = 5m**；1m 仅用于最近一周的精细回测。

### 14.3 日内数据层与 Timeframe 注册表

**新增 `src/data/intraday_manager.py`：**

- 存储：`data/intraday/<symbol>/<interval>.csv`（列：`datetime, open, high, low, close, volume`，`datetime` 含日期+时刻，统一为交易所本地时区）。
- `load_intraday(symbol, interval, start=None, end=None)`：读取并按时间排序。
- `update_intraday(symbol, interval)`：拉取最近窗口，按 `datetime` 去重合并增量落盘。
- `YFinanceIntradayProvider`：实现 Phase 1 已定义的 `QuoteProvider` 接口的批量历史版本；含重试/退避；A 股午休与集合竞价的 bar 对齐处理。

**新增 Timeframe（时间粒度）注册表 `src/data/timeframe_registry.py`：**

- 把 `1m / 5m / 15m / 30m / 60m / 1d` 注册为一等公民（用户："日内决策也是需要注册的一种资产"）。
- 每个 Timeframe 携带：`interval` 字符串、`bars_per_day`、`yf_max_lookback`、`session_minutes`、对齐规则。
- CLI/回测/策略通过注册表发现与组合，避免散落的魔法字符串。

### 14.4 日内卖出择时策略（可注册资产）+ 模型复用

**新增 `src/strategies/intraday/` 与 `IntradayStrategyRegistry`：**

每个日内策略是一个**已注册资产**，输入"日内特征 + 持仓上下文 + 入场信息"，在每个 bar 输出 `hold/sell/scale`。内置：

- `take_profit_stop`：固定 `+X%` 止盈 / `-Y%` 止损 / 跟踪止损。
- `time_decay_exit`：尾盘未达标则按收盘价离场（与 Phase 1 `late_session` 兜底一致）。
- `intraday_reversal`：日内指标反转离场（如 5m MACD 死叉 / 跌破 VWAP）。

**模型复用（用户要求"不必每次决策都训练"）：**

- 复用既有 Pipeline 的 `fit/predict` 分离：`fit` 在**会话开始时一次性**完成（基于历史日线或日内），其后每个 5m bar 只调用 `predict()`。
- 新增 `FittedModelCache`，键 `(symbol, model_id, fit_date)`，缓存已拟合的估计器；回测中按交易日仅 `fit` 一次。
- 日内特征只做"增量更新"（滚动窗口指标），不重训。

### 14.5 日内回测器

**新增 `src/portfolio/intraday_backtester.py`：**

- 在 5m（可选 1m）bar 上逐 bar 迭代某交易日（或日期区间）。
- 入场来自日线/组合层（如 `open`/`late_session` 选出的候选），**日内只负责卖出择时**（也可扩展日内加仓）。
- **A 股 T+1 强约束（必须实现）**：当日买入的股票当日不可卖出。日内卖出择时只能作用于
  **昨日及更早结转的持仓**；当日新建仓位锁定至次日。需用 `available_to_sell`（= 持仓 − 当日买入）
  显式建模，并写测试固化（买入后同日任何卖出信号都不得成交）。
  > 注：日线级回测因每标的每日 ≤1 笔、卖出只动用历史持仓，T+1 天然满足（已实测 0 违规）；
  > 日内级才需要显式锁仓。
- **成交价默认 bar `close`**；无前视：在 bar t 收盘形成信号，在 bar t 收盘成交（或 t+1 开盘，可配置）。
- 复用组合分配与风险上限（单股/总仓位/最低现金）。
- 输出：逐笔交易（含**持有时长、卖出时点**）、日内最大回撤、回撤次数、胜率、择时统计、合并权益曲线。

### 14.6 成交价现实化（修正 Phase 1 的开盘价成交）

- 在**日线** `PortfolioBacktester` 与**日内**回测器中统一新增 `execution_price ∈ {open, close, vwap}`。
- **默认改为 `close`**（用户："收盘价更现实"）。文档需说明权衡：
  - `close`：在 bar t 收盘观察后按该收盘价成交，贴近"看到信号即成交"，但属轻微乐观（close-to-close）。
  - `open`（T+1 开盘）：严格无前视，但用户认为不现实。
  - `vwap`：折中，需 bar 内成交量加权。
- `ComboBacktester` 维持现状（T+1 开盘）以免影响既有结果；仅组合/日内回测器支持新选项。

### 14.7 CLI / API / WebUI（回测向）

- CLI：`portfolio intraday-backtest --interval 5m --date 2026-06-18 [--symbols ...] [--exec-price close]`；`data intraday-update [SYMBOL] --interval 5m`。
- API：`/api/intraday_backtest`、`/api/intraday_data`（只读历史日内）。
- WebUI：日内 K 线 + 卖出择时回放面板（复用现有回测可视化组件）。

### 14.8 任务拆分（TDD，承接第 10 节，从 Task 9 起）

#### Task 9：日内数据层与 Timeframe 注册表
- 文件：`src/data/intraday_manager.py`、`src/data/timeframe_registry.py`、`tests/test_intraday_data.py`
- [ ] 失败测试：从 fixture CSV 加载日内数据并按时间排序。
- [ ] 失败测试：增量更新按 `datetime` 去重合并。
- [ ] 失败测试：Timeframe 注册与查询（5m 的 bars_per_day / 回溯上限）。
- [ ] 实现 `load_intraday / update_intraday / YFinanceIntradayProvider`（含重试）。
- [ ] 实现 Timeframe 注册表。
- [ ] `pytest tests/test_intraday_data.py -q`。

#### Task 10：拟合模型缓存（fit 一次、predict 每 bar）
- 文件：`src/portfolio/fitted_model_cache.py`、`tests/test_fitted_model_cache.py`
- [ ] 失败测试：同一 `(symbol, model, fit_date)` 只 `fit` 一次（用计数桩验证）。
- [ ] 失败测试：跨 bar 复用同一拟合模型，`predict` 多次。
- [ ] 实现缓存并接入。
- [ ] `pytest tests/test_fitted_model_cache.py -q`。

#### Task 11：日内卖出择时策略注册表
- 文件：`src/strategies/intraday/`、`src/strategies/intraday_registry.py`、`tests/test_intraday_strategies.py`
- [ ] 失败测试：`take_profit_stop` 命中止盈/止损/跟踪止损的卖出时点。
- [ ] 失败测试：`time_decay_exit` 尾盘未达标按收盘离场。
- [ ] 失败测试：注册表可发现并创建日内策略。
- [ ] 实现内置策略与注册表。
- [ ] `pytest tests/test_intraday_strategies.py -q`。

#### Task 12：可配置成交价 — ✅ 已完成（vwap 留待日内）
- 文件：`src/portfolio/backtester.py`、`tests/test_portfolio_backtester.py`
- [x] `PortfolioBacktester(execution_price=...)`，默认 `close`；CLI `--exec-price`。
- [x] `close` 用截至当日完整 bar 决策、按收盘成交；`open` 复现旧 T 开盘语义（向后兼容）。
- [x] 实测：2026H1 close +5.76%/-2.27%，open +7.04%/-1.50%（开盘价偏乐观）。
- [ ] `vwap` 分支留待日内回测器一并实现。

#### Task 13：日内回测器
- 文件：`src/portfolio/intraday_backtester.py`、`tests/test_intraday_backtester.py`
- [ ] 失败测试：单标的单日 5m 数据上，止盈在正确 bar 触发卖出。
- [ ] 失败测试：无前视（bar t 信号不得使用 t+1 数据）。
- [ ] 失败测试：组合风险上限在日内仍生效。
- [ ] 失败测试：输出含持有时长与卖出时点。
- [ ] 实现并接入注册表/缓存/成交价。
- [ ] `pytest tests/test_intraday_backtester.py -q`。

#### Task 14：CLI / API / WebUI（回测向）
- 文件：`src/cli/commands/portfolio_cmd.py`（加 `intraday-backtest`）、`src/cli/commands/data_cmd.py`（加 `intraday-update`）、`src/api_server.py`、前端、`tests/test_intraday_cli_api.py`
- [ ] 失败测试：CLI `portfolio intraday-backtest` 注册与运行（用小 fixture）。
- [ ] 失败测试：`/api/intraday_backtest`、`/api/intraday_data`。
- [ ] 实现命令、端点与 WebUI 面板。
- [ ] 运行目标测试 + `node --check`。

#### Task 15：文档与全量验证
- 文件：`docs/intraday_backtest.md`、更新 README / `docs/portfolio_decision.md`
- [ ] 记录日内数据 schema、回溯限制、成交价语义、注册表用法。
- [ ] 全量：`pytest tests -q`、`tests/test_backend.py`、`py_compile`、`node --check`。

### 14.9 风险与缓解

- **yfinance 日内不稳定/限频** → 增量缓存 + 重试退避；预留 `akshare/eastmoney` 备用提供者（可选依赖，置于同一 Provider 接口后）。
- **1m 仅 7 天历史** → 长历史 1m 回测不可行；默认 5m，1m 仅近一周。
- **A 股午休/集合竞价对齐** → Timeframe 携带 session 规则，bar 对齐显式处理，并写测试固化。
- **无前视不变量**（延续第 13 节）：日内 bar t 的决策只能用 ≤ t 的数据；成交价语义需显式、可测。

> **14.6 进度：成交价现实化已先行落地。** `PortfolioBacktester` 新增 `execution_price ∈ {close, open}`，
> **默认 `close`**（CLI `--exec-price`）。2026H1 实测：close +5.76% / 回撤 -2.27%，open +7.04% / 回撤 -1.50%
> —— 印证开盘价成交偏乐观。日内回测器将沿用同一语义。

---

## 15. 无前视纪律与收益优化（用户反馈固化，2026-06-19）

### 15.1 现象

组合滚动决策（close 成交 +5.76%）显著**逊于集中单股**（如 002156 单股 +63%）。用户判定"这不好"，
要求：**谨防前视误差，但要优化决策收益率；调参也不能基于前视误差。**

### 15.2 根因诊断（必须正视）

1. **基准本身被前视污染**：`data/best_combos.json` 是在与回测**重叠/同区间**上 `scan/analyze` 选出的最优组合。
   用它跑同一区间属**样本内选择偏差**。所以"单股 +63%"不是诚实基准，组合与单股的对比当前并不公平。
2. **敞口被压制**：风险上限（总 40% / 单股 10% / 最低现金 20%）把平均敞口压到 ~11%，收益被结构性稀释。
3. **选股策略本身有问题（用户判定，非仅分配问题）**：资金被"摊到弱标的"说明**选择/排序逻辑就不对**——
   当前 `final_rank = opportunity - risk` 里 risk 权重过高、opportunity 信号弱，
   导致几乎所有通过闸门的标的都被等同对待并入选。问题在**选股**上游，不只是下游"集中度"旋钮：
   - 应**只选真正有（样本外）优势的少数高确信标的**，而非把所有未被拒的都纳入。
   - 排序应纳入**前瞻一致、样本外可验证**的预期收益信号，而非主要靠历史风险度量。
   - 组合选择须 **walk-forward**（见 Task 16）；否则"选得对不对"无从诚实判断。

### 15.3 必须遵守的原则

- **回测无前视**：bar t 决策只用 ≤ t 数据；成交价语义显式、可测（已对 close/open 固化）。
- **调参 / 组合选择同样不得前视**：一切参数与组合的选择必须 **walk-forward / 滚动样本外**——
  在每个再平衡点，只用该点**之前**的数据选组合/调参，测试窗口只读用、不回看。
  禁止在测试区间上直接挑最优组合或网格搜参。
- **公平基准**：组合 vs 单股、组合 vs 买入持有，都必须在**同一套样本外**协议下比较，否则结论无效。
- **收益优化只在风险约束内进行**：可调 `final_rank` 的 opportunity 权重、动态/分档仓位上限、
  按预测强度做**集中度可调**的分配（仍受单股上限与回撤事件约束）。
- **评估指标用样本外**收益 / 夏普 / 回撤，而非样本内最优值。

### 15.4 追加任务（并入 Phase 2，从 Task 16 起）

#### Task 16：Walk-forward 组合选择器 — ✅ 已完成
- [x] 失败测试：在再平衡点 t，仅用 `< t` 的数据选出组合（断言训练窗口 end < cutoff）。
- [x] 实现滚动样本外组合选择（`src/portfolio/walkforward.py`：`WalkForwardSelector` + `ComboChoice` + `combo_for_date`）。
- [x] 组合回测消费 walk-forward 计划：`PortfolioBacktester(combo_plan=...)`，按交易日解析当时生效组合（随再平衡切换）。
- [x] CLI：`portfolio backtest --walk-forward [--wf-train-days N --wf-step-days N]`。
- [x] 测试：`tests/test_walkforward.py`、`tests/test_portfolio_backtester.py`（含 T+1 不变量与计划切换）。

> 要点：`select_at(symbol, cutoff)` 训练窗口 `[cutoff-train_window, cutoff-1]`，严格早于 cutoff；
> `build_plan` 在再平衡点为每只标的产出按时间排列的 `ComboChoice`；评分默认 Sharpe（支持 `return` / `return_dd`）。

#### Task 17：收益感知**选股** + 集中分配（修正"摊到弱标的"）
> 用户判定：摊到弱标的=选股策略不对。故先修选择，再谈分配。
- [ ] 失败测试：排序纳入样本外可验证的预期收益信号后，弱标的不再入选（仅 Top-K 高确信入选）。
- [ ] 失败测试：新增"最大持仓数 / 入选信号下限"参数，控制选股**广度**（少而精）。
- [ ] 失败测试：闸门通过且入选的标的，资金按预测强度**集中**而非均摊。
- [ ] 失败测试：集中分配仍满足单股上限 / 总仓位 / 最低现金 / 回撤事件约束。
- [ ] 实现：调整 `final_rank` 权重、入选门槛、Top-K 广度、集中度；用**样本外**收益对比均摊 vs 少而精。

#### Task 18：无前视参数搜索框架
- [ ] 失败测试：参数搜索的"选择"只发生在样本内子区间，"评估"在其后的样本外子区间。
- [ ] 实现 walk-forward 调参（滚动训练/验证切分），输出样本外绩效。
- [ ] 明确禁止在测试集上调参的 API 约定与文档。

#### Task 19：公平基准对照
- [ ] 失败测试：单股、买入持有、组合三者均在同一 walk-forward 协议下评估。
- [ ] 输出对照表（样本外收益 / 回撤 / 回撤次数 / 夏普），让"组合是否真的更好"可被诚实回答。

### 15.5 验收

- 组合在**样本外**协议下，目标是：在可比敞口下回撤更低、回撤次数更少，且收益不被无谓稀释；
  若仍明显逊于诚实（样本外）的单股基准，则说明分配/选择需继续改进——但**绝不允许**用前视调参把数字做好看。
