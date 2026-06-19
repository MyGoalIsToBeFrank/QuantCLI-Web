"""
后端模块自测脚本

覆盖当前架构核心组件：
  - Config
  - DataManager / StockRegistry
  - FactorRegistry / TargetRegistry
  - ModelRegistry / PipelineRegistry / StrategyRegistry
  - ComboBacktester
  - 主要 CLI 命令 import
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

from src.data.data_manager import load_stock, update_stock, list_stock_files
from src.data.stock_registry import REGISTRY
from src.factors.registry import FACTOR_REGISTRY
from src.factors.target_registry import TARGET_REGISTRY
from src.model_registry import MODEL_REGISTRY
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.backtest.combo_backtester import ComboBacktester
from src.pipeline_configs import PIPELINE_CONFIG_MANAGER
from src.analysis.best_combo_registry import BestComboRegistry

TEST_OUTPUT_DIR = Path(tempfile.gettempdir()) / 'quant_strategy_platform_tests'


def test_data():
    print('=== 1. 数据 ===')
    print('股票池:', REGISTRY.list_symbols())
    df = load_stock('002156.SZ')
    print(f'002156.SZ 数据条数: {len(df)}, 列: {list(df.columns)}')
    print(df.tail(2))


def test_factors_targets():
    print('\n=== 2. 因子 / 目标注册表 ===')
    print('因子:', [f['name'] for f in FACTOR_REGISTRY.list()])
    print('目标:', [t['name'] for t in TARGET_REGISTRY.list()])


def test_registries():
    print('\n=== 3. 模型 / Pipeline / 策略注册表 ===')
    print('模型:', MODEL_REGISTRY.list_names())
    print('Pipeline:', PIPELINE_REGISTRY.list_names())
    print('Strategy:', STRATEGY_REGISTRY.list_names())


def test_pipeline_predict():
    print('\n=== 4. Pipeline 端到端预测 ===')
    df = load_stock('002156.SZ')
    for name in PIPELINE_REGISTRY.list_names():
        pipeline = PIPELINE_REGISTRY.create(name)
        pipeline.fit(df)
        pred = pipeline.predict()
        assert 'prob_bull' in pred, f'{name} 缺少 prob_bull'
        assert 'signal' in pred, f'{name} 缺少 signal'
        print(f'{name}: signal={pred["signal"]}, prob_bull={pred["prob_bull"]:.4f}')


def test_backtest():
    print('\n=== 5. 组合回测 ===')
    bt = ComboBacktester('002156.SZ', 'ma_dual', 'prob_position',
                         initial_capital=100000, fee_per_trade=5)
    result = bt.run(start_date='2025-12-18', end_date='2026-06-17')
    m = result['metrics']
    print(f"收益率: {m['total_return_pct']:.2f}%, 最大回撤: {m['max_drawdown_pct']:.2f}%, "
          f"夏普: {m['sharpe']:.3f}, 交易次数: {m['trade_count']}")


def test_best_combo_registry():
    print('\n=== 6. 最佳组合注册表 ===')
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = BestComboRegistry(path=TEST_OUTPUT_DIR / 'best_combos_test.json')
    test_metrics = {
        'total_return_pct': 1.0,
        'max_drawdown_pct': -0.5,
        'trade_count': 2,
        'sharpe': 0.3
    }
    registry.set(
        symbol='002156.SZ',
        pipeline_name='ma_dual',
        strategy_id='prob_position',
        metrics=test_metrics,
        time_range={'start': '2025-12-18', 'end': '2026-06-17'}
    )
    combo = registry.get('002156.SZ')
    assert combo is not None
    print('已保存组合:', combo['pipeline_name'], '+', combo['strategy_id'])


def test_cli_imports():
    print('\n=== 7. CLI 入口可导入 ===')
    from src.cli.main import main
    from src.cli.commands import (
        data_cmd, analyze_cmd, scan_cmd, backtest_cmd,
        decide_cmd, list_cmd, fundamental_cmd, chart_cmd
    )
    print('CLI 模块导入成功')


if __name__ == '__main__':
    test_data()
    test_factors_targets()
    test_registries()
    test_pipeline_predict()
    test_backtest()
    test_best_combo_registry()
    test_cli_imports()
    print('\n=== 所有后端模块测试通过 ===')
