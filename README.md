# 量化策略平台

> 一个支持**多股票、多 Pipeline、多策略**的量化研究与实盘决策平台。CLI 与 Web UI 共享同一套底层架构，所有能力都通过 Pipeline × Strategy × Model 注册表组合实现。

---

## 快速开始

### 环境

- Python 3.10+
- Windows（推荐）/ 任何能运行 Flask 的环境

### 启动 Web UI

```bash
QuantWebUI.bat
```

会自动创建虚拟环境、安装依赖并打开浏览器访问 `http://127.0.0.1:5000`。

底层等价于 `scripts\start.bat`。

> 所有内部路径均使用 `pathlib.Path` 相对管理，项目可以在任意磁盘或文件夹名下运行。

### 今日决策（CLI）

```bash
# 使用已保存的最佳组合
QuantCLI.bat decide 002156.SZ --open 68.0

# 等价于调用 scripts 目录下的包装脚本
scripts\decide.bat 002156.SZ --open 68.0
```

直接运行 `QuantCLI.bat`（不带参数）会显示常用命令提示。

---

## 核心概念

```
CSV / Yahoo Finance
       │
       ▼
load_stock(symbol) ──► Pipeline.fit(df) ──► Pipeline.predict(row)
                              │                    │
                              ▼                    ▼
                   FactorRegistry /         Strategy.decide()
                   TargetRegistry /                │
                   ModelRegistry                 ▼
                                       target_position
                                               │
                                               ▼
                                    calculate_trade_shares()
                                               │
                                               ▼
                                       回测 / 实盘决策
```

- **Pipeline**：单一预测管线，例如 `ma_dual`、`macd`、`rf_ma_dual`。
- **Strategy**：把预测映射为仓位，例如 `prob_position`、`macd_cross`、`low_risk`。
- **Model**：Pipeline 内部的预测实现，例如 `dual_logistic`、`dual_random_forest`。
- **Factor / Target**：注册在 `src/factors/` 下的可复用因子与监督目标。

---

## CLI 用法

Windows 下推荐通过根目录的 `QuantCLI.bat` 调用，所有子命令的同名 `.bat` 包装脚本位于 `scripts/` 目录，可直接省略 `strategy` 前缀：

| 命令 | 根目录入口示例 | scripts 目录等价示例 |
|------|----------------|----------------------|
| `analyze` | `QuantCLI.bat analyze 002156.SZ --start 2024-06-01 --end 2026-06-17 --max-drawdown 5` | `scripts\analyze.bat 002156.SZ --start 2024-06-01 --end 2026-06-17 --max-drawdown 5` |
| `scan` | `QuantCLI.bat scan 002156.SZ --start 2024-06-01 --end 2026-06-17` | `scripts\scan.bat 002156.SZ --start 2024-06-01 --end 2026-06-17` |
| `backtest` | `QuantCLI.bat backtest 002156.SZ ma_dual prob_position --start 2025-12-18 --end 2026-06-17` | `scripts\backtest.bat 002156.SZ ma_dual prob_position --start 2025-12-18 --end 2026-06-17` |
| `decide` | `QuantCLI.bat decide 002156.SZ --open 68.0` | `scripts\decide.bat 002156.SZ --open 68.0` |
| `portfolio` | `QuantCLI.bat portfolio decide --mode close_after_market` | `scripts\portfolio.bat backtest --start 2026-01-01 --end 2026-06-19 --capital 100000` |
| `chart` | `QuantCLI.bat chart 002156.SZ --ma 5,20 --height 20` | `scripts\chart.bat 002156.SZ --ma 5,20 --height 20` |
| `list` | `QuantCLI.bat list pipelines` | `scripts\list.bat pipelines` |
| `data` | `QuantCLI.bat data list` | `scripts\data.bat list` |
| `fundamental` | `QuantCLI.bat fundamental check 002156.SZ` | `scripts\fundamental.bat check 002156.SZ` |
| `help` | `QuantCLI.bat help backtest` | `scripts\strategy.bat help backtest` |

- **交互式候选**：`backtest`、`chart`、`fundamental check/show/prompt/report` 等命令在省略股票代码（或 Pipeline/Strategy）时，会自动列出候选并提示输入序号或代码。
- **帮助命令**：`QuantCLI.bat help` 查看全局帮助，`QuantCLI.bat help <命令>` 查看具体命令示例。
- **颜色开关**：默认启用 ANSI 颜色；`QuantCLI.bat --no-color <命令>` 可禁用颜色。
- **自动保存**：`analyze` 与 `scan` 默认将最佳组合保存到 `data/best_combos.json`；使用 `--no-save` 可取消保存。

省略股票代码时，`analyze`、`scan`、`decide` 默认作用于所有注册股票（`decide` 优先使用已保存最佳组合的股票）。

---

## Web UI

`QuantWebUI.bat`（或 `scripts\start.bat`）启动的 Web 界面与 CLI 共用同一套 API：

- **仪表盘**：选择股票 → 查看 K 线、当前最佳组合、运行回测/决策。
- **策略分析**：按季度滚动回测所有组合，保存最佳组合。
- **批量报告**：一键对所有注册股票生成分析 + 回测 + 今日决策对比表。
- **组合决策**：编辑现金/持仓与风险配置，按盘后/开盘实时/尾盘三种模式生成组合级订单建议与回撤可控的候选排序（详见 `docs/portfolio_decision.md`）。
- **基本面记录**：只读查看由 CLI/Agent 生成的基本面分析记录与报告。

---

## 目录结构

```
quant-strategy-platform/
├── QuantWebUI.bat                 # 根目录入口：启动 Web UI
├── QuantCLI.bat                   # 根目录入口：CLI 统一入口
├── scripts/
│   ├── start.bat                  # 启动 Web UI（被 QuantWebUI.bat 调用）
│   ├── run_update.bat             # 一键更新所有股票数据
│   ├── strategy.bat               # CLI 统一入口（被 QuantCLI.bat 调用）
│   ├── analyze.bat / scan.bat / backtest.bat / decide.bat / chart.bat / list.bat / data.bat / fundamental.bat
│   │                              # 同名包装脚本，省略 strategy 前缀
│   └── test_backend.bat           # 后端自测入口（可选）
├── src/
│   ├── api_server.py              # Flask API 服务器
│   ├── registry_base.py           # 通用注册表基类
│   ├── model_registry.py          # 模型注册表
│   ├── pipeline_registry.py       # Pipeline 注册表
│   ├── strategy_registry.py       # Strategy 注册表
│   ├── pipeline_configs.py        # Pipeline 配置管理
│   ├── strategy.py                # 通用交易函数
│   ├── models/                    # 预测模型
│   ├── data/                      # 数据管理
│   ├── factors/                   # 因子与目标注册表
│   ├── pipelines/                 # Pipeline 实现
│   ├── strategies/                # Strategy 实现
│   ├── backtest/                  # 回测系统
│   ├── analysis/                  # 策略分析
│   ├── fundamental/               # 基本面记录
│   ├── cli/                       # CLI
│   └── frontend/                  # Web 前端
├── tests/
│   └── test_backend.py            # 后端自测脚本
├── data/
│   ├── stocks/                    # 多股票日线 CSV
│   ├── pipeline_configs.json      # Pipeline 配置
│   ├── best_combos.json           # 每只股票最佳组合
│   └── fundamental_records.json   # 基本面分析记录
├── reports/                       # 各类报告
│   ├── fundamental/               # 基本面分析报告
│   ├── backtest/                  # 回测报告
│   └── optimization_report.md     # 优化报告
├── docs/                          # 文档与参考资料
│   └── reference/                 # 外部参考资料（网页归档等）
├── README.md                      # 本文件
├── AGENTS.md                      # 开发者指南
├── 技术白皮书.md                   # 技术白皮书
└── requirements.txt               # 依赖
```

---

## 扩展

新增模型、因子、Pipeline、Strategy 的方法见 `AGENTS.md`。

---

## 免责声明

本项目为量化研究与学习用途，不构成投资建议。股市有风险，决策需谨慎。
