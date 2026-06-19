# AGENTS.md — 量化策略平台

> 面向 AI Agent 与开发者的项目指南：结构、接口、扩展方式与常见任务。

---

## 1. 目录结构

```
quant-strategy-platform/
├── QuantWebUI.bat                 # 根目录入口：启动 Web UI
├── QuantCLI.bat                   # 根目录入口：CLI 统一入口
├── scripts/
│   ├── start.bat / run_update.bat / strategy.bat
│   ├── analyze.bat / scan.bat / backtest.bat / decide.bat / chart.bat / list.bat / data.bat / fundamental.bat
│   └── test_backend.bat           # 后端自测入口
├── src/
│   ├── api_server.py              # Flask Web API
│   ├── registry_base.py           # 通用注册表基类
│   ├── model_registry.py          # ModelRegistry
│   ├── pipeline_registry.py       # PipelineRegistry
│   ├── strategy_registry.py       # StrategyRegistry
│   ├── pipeline_configs.py        # Pipeline 配置管理
│   ├── strategy.py                # calculate_trade_shares
│   ├── models/                    # 预测模型实现
│   ├── data/                      # 数据管理
│   ├── factors/                   # 因子与目标注册表
│   ├── pipelines/                 # Pipeline 实现
│   ├── strategies/                # Strategy 实现
│   ├── backtest/                  # ComboBacktester / ComboScanner / metrics
│   ├── analysis/                  # QuarterlyAnalyzer / BestComboRegistry
│   ├── fundamental/               # FundamentalRecords
│   ├── cli/                       # CLI
│   └── frontend/                  # Web UI
├── tests/                         # 后端自测脚本
├── data/                          # 数据与配置
├── reports/                       # 报告（基本面 / 回测 / 优化）
└── docs/                          # 文档与参考资料
```

---

## 2. 核心架构

### 2.1 数据流

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

### 2.2 注册表

所有注册表继承 `SimpleRegistry`，统一提供：

```python
REGISTRY.register(cls)
REGISTRY.get(name)
REGISTRY.create(name, *args, **kwargs)
REGISTRY.list_names()
```

- `FactorRegistry`：通过装饰器注册因子函数。
- `TargetRegistry`：通过装饰器注册监督目标函数。
- `ModelRegistry`：注册 `BaseModel` 子类。
- `PipelineRegistry`：注册 `BasePipeline` 子类。
- `StrategyRegistry`：注册 `BaseStrategy` 子类。

### 2.3 Pipeline 配置

`data/pipeline_configs.json` 由 `PipelineConfigManager` 管理。一个配置示例：

```json
{
  "ma_dual_v1": {
    "name": "MA 双模型 Logistic",
    "factors": [
      {"name": "sma", "params": {"window": 20}, "output_col": "ma20"},
      {"name": "zscore", "params": {"window": 20}, "output_col": "z20"}
    ],
    "model": {"type": "dual_logistic", "params": {"w_ma5": 0.6, "w_ma20": 0.4}},
    "targets": [
      {"name": "ma_direction", "params": {"window": 5}, "output_col": "target_ma5"}
    ],
    "feature_cols": ["ma20", "z20"],
    "predictions": {"prob_bull": "prob_combined", "score": "score", "signal": "signal"}
  }
}
```

`ConfigurablePipeline` 读取配置后：
1. 用 `FactorRegistry` 计算因子。
2. 用 `TargetRegistry` 生成目标。
3. 用 `ModelRegistry` 创建模型。
4. 调用 `model.fit(df)` / `model.predict(row)`。

---

## 3. 扩展指南

### 3.1 添加模型

```python
# src/models/my_model.py
from .base import BaseModel

class MyModel(BaseModel):
    name = 'my_model'

    def fit(self, df): ...
    def predict(self, row): return {'prob_bull': ..., 'score': ..., 'signal': ...}
```

在 `src/model_registry.py` 注册，并在 `data/pipeline_configs.json` 中设置 `model.type = "my_model"`。

### 3.2 添加因子

```python
# src/factors/definitions.py
@FACTOR_REGISTRY.register(
    name='my_factor',
    required_columns=['close'],
    default_params={'window': 20},
    description='...'
)
def my_factor(df, window=20):
    return df['close'].rolling(window=window).mean()
```

### 3.3 添加 Pipeline

```python
# src/pipelines/my_pipeline.py
from src.pipelines.configurable import ConfigurablePipeline

class MyPipeline(ConfigurablePipeline):
    name = 'my_pipeline'
    config_id = 'my_config_v1'
```

在 `src/pipeline_registry.py` 注册。

### 3.4 添加 Strategy

```python
# src/strategies/my_strategy.py
from .base import BaseStrategy

class MyStrategy(BaseStrategy):
    name = 'my_strategy'
    accepted_keys = {'prob_bull'}

    def decide(self, prediction, context):
        ...
        return {'action': 'buy', 'target_position': 1.0, 'note': '...'}
```

在 `src/strategy_registry.py` 注册。

---

## 4. 常见任务

### 本地测试

```bash
.venv\Scripts\python.exe tests\test_backend.py
```

### 查看帮助

```bash
QuantCLI.bat help
QuantCLI.bat help backtest
```

### 回测近半年

```bash
QuantCLI.bat backtest 002156.SZ ma_dual prob_position --start 2025-12-18 --end 2026-06-17
```

### 扫描并保存最佳组合

```bash
QuantCLI.bat scan 002156.SZ --start 2025-12-18 --end 2026-06-17 --max-drawdown 5
```

### 扫描不保存

```bash
QuantCLI.bat scan 002156.SZ --start 2025-12-18 --end 2026-06-17 --max-drawdown 5 --no-save
```

### 重置 Pipeline 配置

```python
from src.pipeline_configs import PIPELINE_CONFIG_MANAGER
PIPELINE_CONFIG_MANAGER.reset_to_defaults()
```

---

## 5. API 列表

Web UI 与 CLI 共用同一套底层逻辑，Flask 暴露以下接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | 股票池 |
| GET | `/api/pipelines` | Pipeline 列表 |
| GET | `/api/strategies` | Strategy 列表 |
| GET | `/api/stock_data?symbol=` | K 线数据 |
| POST | `/api/update_stock` | 更新单只股票 |
| POST | `/api/analyze` | 季度策略分析 |
| GET | `/api/best_combo` | 获取最佳组合 |
| POST | `/api/backtest` | 组合回测 |
| POST | `/api/decide_stock` | 今日决策 |
| POST | `/api/batch_report` | 批量报告 |
| GET | `/api/fundamental_records` | 基本面记录 |
| GET | `/api/fundamental_report` | 基本面报告 |

---

## 6. 注意事项

- 所有配置集中在 `data/pipeline_configs.json`，不再使用全局 `config.json`。
- `data/best_combos.json` 仅保存组合名称与测试区间，不保存实现细节。
- 基本面分析通过 CLI/Agent 触发，Web UI 只读。
