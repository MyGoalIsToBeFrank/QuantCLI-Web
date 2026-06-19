"""
Flask API 服务器

所有接口统一使用：
  - src.data.data_manager
  - src.pipeline_registry / src.strategy_registry
  - src.backtest.combo_backtester
  - src.analysis.quarterly_analyzer / best_combo_registry
  - src.fundamental.records
"""

import os
import sys
import json
import warnings
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_manager import load_stock, update_stock
from src.data.stock_registry import REGISTRY
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.backtest.combo_backtester import ComboBacktester, build_latest_open_decision_frame
from src.strategy import calculate_trade_shares
from src.analysis.quarterly_analyzer import QuarterlyAnalyzer
from src.analysis.best_combo_registry import BestComboRegistry
from src.fundamental.records import FundamentalRecords
from src.portfolio.state import PortfolioStateManager
from src.portfolio.risk import RiskProfileManager
from src.portfolio.decision_engine import PortfolioDecisionEngine
from src.portfolio.schema import DecisionMode

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
app = Flask(__name__, static_folder=FRONTEND_DIR)


def _clean_value(v):
    """将 numpy/pandas 类型转为 Python 原生类型"""
    if hasattr(v, 'item'):
        return v.item()
    return v


def _clean_records(records):
    """清理 records 中的非 JSON 类型"""
    out = []
    for r in records:
        out.append({k: _clean_value(v) for k, v in r.items()})
    return out


# ============================================================
# 静态文件托管
# ============================================================

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


# ============================================================
# 股票池 / 组件列表
# ============================================================

@app.route('/api/stocks', methods=['GET'])
def api_stocks():
    """获取股票池"""
    try:
        stocks = [
            {'symbol': s.symbol, 'name': s.name, 'market': s.market}
            for s in REGISTRY.list_all()
        ]
        return jsonify({'success': True, 'stocks': stocks})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/pipelines', methods=['GET'])
def api_pipelines():
    """获取可用 Pipeline 列表"""
    try:
        return jsonify({'success': True, 'pipelines': PIPELINE_REGISTRY.list_info()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/strategies', methods=['GET'])
def api_strategies():
    """获取可用 Strategy 列表"""
    try:
        return jsonify({'success': True, 'strategies': STRATEGY_REGISTRY.list_info()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# 数据接口
# ============================================================

@app.route('/api/stock_data', methods=['GET'])
def api_stock_data():
    """获取单只股票 K 线数据"""
    try:
        symbol = request.args.get('symbol', '002156.SZ')
        df = load_stock(symbol)

        records = []
        for _, row in df.iterrows():
            records.append({
                'date': str(row['date']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume'])
            })
        return jsonify({'success': True, 'symbol': symbol, 'data': records})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update_stock', methods=['POST'])
def api_update_stock():
    """更新单只股票数据"""
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol')
        if not symbol:
            return jsonify({'success': False, 'message': '缺少 symbol'}), 400
        result = update_stock(symbol)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# 分析 / 回测 / 决策
# ============================================================

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """季度策略分析"""
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol')
        start = data.get('start', '2024-06-01')
        end = data.get('end') or datetime.now().date().isoformat()
        pipelines = data.get('pipelines')
        strategies = data.get('strategies')
        max_drawdown = data.get('max_drawdown')
        save = data.get('save', False)

        if not symbol:
            return jsonify({'success': False, 'message': '缺少 symbol'}), 400

        analyzer = QuarterlyAnalyzer()
        result = analyzer.analyze_symbol(
            symbol, start, end,
            pipelines=pipelines,
            strategies=strategies,
            max_drawdown_pct=max_drawdown
        )

        if save:
            registry = BestComboRegistry()
            registry.update_from_analysis(
                result,
                time_range={'start': start, 'end': end}
            )

        summary = analyzer.summarize(result)
        return jsonify({
            'success': True,
            'symbol': symbol,
            'quarters': [
                {
                    'quarter': q['quarter'],
                    'start': q['start'],
                    'end': q['end'],
                    'best': q['best']
                }
                for q in result['quarters']
            ],
            'summary': summary.to_dict(orient='records')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/best_combo', methods=['GET'])
def api_best_combo():
    """获取某股票最佳组合"""
    try:
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({'success': False, 'message': '缺少 symbol'}), 400
        registry = BestComboRegistry()
        combo = registry.get(symbol)
        return jsonify({'success': True, 'symbol': symbol, 'combo': combo})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/backtest', methods=['POST'])
def api_backtest():
    """组合回测"""
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol')
        pipeline_name = data.get('pipeline')
        strategy_name = data.get('strategy')

        if not symbol or not pipeline_name or not strategy_name:
            return jsonify({
                'success': False,
                'message': '缺少 symbol / pipeline / strategy'
            }), 400

        start = data.get('start')
        end = data.get('end')
        stop_loss = data.get('stop_loss')
        stop_loss_pct = stop_loss / 100.0 if stop_loss is not None else None
        capital = data.get('capital', 100000.0)
        fee = data.get('fee', 5.0)
        lot = data.get('lot', 100)

        bt = ComboBacktester(
            symbol, pipeline_name, strategy_name,
            initial_capital=capital,
            fee_per_trade=fee,
            lot_size=lot,
            stop_loss_pct=stop_loss_pct
        )
        result = bt.run(start_date=start, end_date=end)
        m = result['metrics']
        records = result['records'].to_dict(orient='records')

        return jsonify({
            'success': True,
            'mode': 'combo',
            'metrics': _clean_value(m),
            'records': _clean_records(records)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/decide_stock', methods=['POST'])
def api_decide_stock():
    """单只股票今日决策"""
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol')
        if not symbol:
            return jsonify({'success': False, 'message': '缺少 symbol'}), 400

        registry = BestComboRegistry()
        combo = registry.get(symbol)
        pipeline_name = data.get('pipeline') or (
            combo.get('pipeline_name') or combo.get('pipeline') if combo else None
        )
        strategy_name = data.get('strategy') or (
            combo.get('strategy_id') or combo.get('strategy') if combo else None
        )

        if not pipeline_name or not strategy_name:
            return jsonify({'success': False, 'message': '没有可用的最佳组合'}), 400

        raw_df = load_stock(symbol)
        today = datetime.now().date()
        last_date = raw_df['date'].iloc[-1]

        t_open = data.get('open')
        if t_open is None:
            if str(last_date) == str(today):
                t_open = float(raw_df['open'].iloc[-1])
            else:
                t_open = float(raw_df['close'].iloc[-1])
        t_open = float(t_open)

        decision_mode = data.get('decision_mode', 'auto')
        use_open = (
            decision_mode == 'open' or
            (decision_mode == 'auto' and (data.get('open') is not None or str(last_date) == str(today)))
        )
        fit_df = build_latest_open_decision_frame(raw_df, t_open, today) if use_open else raw_df

        pipeline = PIPELINE_REGISTRY.create(pipeline_name)
        strategy = STRATEGY_REGISTRY.create(strategy_name)
        pipeline.fit(fit_df)
        pred = pipeline.predict()

        t_minus_1_close = float(raw_df['close'].iloc[-1]) if use_open else (
            float(raw_df['close'].iloc[-2]) if len(raw_df) > 1 else t_open
        )
        gap_pct = (t_open / t_minus_1_close - 1) * 100

        capital = data.get('capital', 100000.0)
        fee = data.get('fee', 5.0)
        lot = data.get('lot', 100)
        context = {
            'current_position': 0.0,
            'cash': capital,
            'shares': 0,
            'open_price': t_open,
            'close_price': float(raw_df['close'].iloc[-1]),
            'prev_close': t_minus_1_close,
            'fee_per_trade': fee,
            'lot_size': lot,
            'signal_threshold': 0.10
        }
        decision = strategy.decide(pred, context)
        target_position = decision['target_position']
        trade_shares = calculate_trade_shares(
            capital, 0, t_open, target_position, fee, lot
        )

        action = 'hold'
        if trade_shares > 0:
            action = 'buy'
        elif trade_shares < 0:
            action = 'sell'

        return jsonify({
            'success': True,
            'symbol': symbol,
            'date': str(today),
            'pipeline': pipeline_name,
            'strategy': strategy_name,
            'decision_mode': 'open' if use_open else 'close',
            'open': t_open,
            'gap_pct': gap_pct,
            'prediction': {k: _clean_value(v) for k, v in pred.items()},
            'decision': {
                'action': action,
                'target_position': target_position,
                'trade_shares': trade_shares,
                'note': decision['note']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/batch_report', methods=['POST'])
def api_batch_report():
    """批量综合报告：分析 + 回测 + 决策"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols')
        start = data.get('start', '2024-06-01')
        end = data.get('end') or datetime.now().date().isoformat()
        max_drawdown = data.get('max_drawdown', 5.0)
        save = data.get('save', False)
        capital = data.get('capital', 100000.0)
        fee = data.get('fee', 5.0)
        lot = data.get('lot', 100)

        if not symbols:
            symbols = REGISTRY.list_symbols()
        elif isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(',')]

        analyzer = QuarterlyAnalyzer()
        registry = BestComboRegistry()
        analysis_rows = []
        backtest_rows = []
        decide_rows = []

        for symbol in symbols:
            try:
                result = analyzer.analyze_symbol(
                    symbol, start, end,
                    max_drawdown_pct=max_drawdown
                )
                q = result['quarters'][-1]
                best = q['best']
                relaxed = q.get('constraint_relaxed', False)
                if best and best.get('total_return_pct', -999) > -900:
                    if save:
                        registry.update_from_analysis(
                            result,
                            time_range={'start': start, 'end': end}
                        )
                    analysis_rows.append({
                        'symbol': symbol,
                        'pipeline': best['pipeline'],
                        'strategy': best['strategy'],
                        'total_return_pct': best['total_return_pct'],
                        'max_drawdown_pct': best['max_drawdown_pct'],
                        'sharpe': best['sharpe'],
                        'trade_count': best['trade_count'],
                        'relaxed': relaxed
                    })

                    bt = ComboBacktester(
                        symbol, best['pipeline'], best['strategy'],
                        initial_capital=capital, fee_per_trade=fee, lot_size=lot
                    )
                    bt_res = bt.run(start_date=start, end_date=end)
                    bm = bt_res['metrics']
                    backtest_rows.append({
                        'symbol': symbol,
                        'pipeline': best['pipeline'],
                        'strategy': best['strategy'],
                        'total_return_pct': bm['total_return_pct'],
                        'max_drawdown_pct': bm['max_drawdown_pct'],
                        'sharpe': bm['sharpe'],
                        'trade_count': bm['trade_count'],
                        'win_rate': bm['win_rate'],
                        'final_value': bm['final_value'],
                        'total_fees': bm['total_fees']
                    })

                    raw_df = load_stock(symbol)
                    today = datetime.now().date()
                    last_date = raw_df['date'].iloc[-1]
                    pipeline = PIPELINE_REGISTRY.create(best['pipeline'])
                    strategy = STRATEGY_REGISTRY.create(best['strategy'])
                    pipeline.fit(raw_df)
                    pred = pipeline.predict()
                    t_open = float(raw_df['open'].iloc[-1]) if str(last_date) == str(today) else float(raw_df['close'].iloc[-1])
                    ctx = {
                        'current_position': 0.0, 'cash': capital, 'shares': 0,
                        'open_price': t_open, 'close_price': float(raw_df['close'].iloc[-1]),
                        'prev_close': float(raw_df['close'].iloc[-2]) if len(raw_df) > 1 else t_open,
                        'fee_per_trade': fee, 'lot_size': lot, 'signal_threshold': 0.10
                    }
                    decision = strategy.decide(pred, ctx)
                    target = decision['target_position']
                    shares = calculate_trade_shares(capital, 0, t_open, target, fee, lot)
                    action = '持有'
                    if shares > 0:
                        action = f'买入{shares}'
                    elif shares < 0:
                        action = f'卖出{abs(shares)}'
                    decide_rows.append({
                        'symbol': symbol,
                        'open': t_open,
                        'target_position': target,
                        'action': action,
                        'note': decision['note']
                    })
            except Exception as e:
                analysis_rows.append({'symbol': symbol, 'error': str(e)})

        return jsonify({
            'success': True,
            'start': start,
            'end': end,
            'max_drawdown': max_drawdown,
            'analysis': analysis_rows,
            'backtest': backtest_rows,
            'decision': decide_rows
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# 组合决策（portfolio）
# ============================================================

@app.route('/api/portfolio_state', methods=['GET'])
def api_portfolio_state_get():
    """获取组合账户状态及持仓最新价格。"""
    try:
        state = PortfolioStateManager().load()
        prices = {}
        for symbol in state.positions:
            try:
                prices[symbol] = float(load_stock(symbol)['close'].iloc[-1])
            except Exception:
                prices[symbol] = None
        data = state.to_dict()
        data['prices'] = prices
        data['estimated_equity'] = state.total_equity(
            {s: p for s, p in prices.items() if p})
        return jsonify({'success': True, 'state': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/portfolio_state', methods=['PUT'])
def api_portfolio_state_put():
    """整体更新组合状态（现金 + 持仓 + lot_size）。"""
    try:
        data = request.get_json() or {}
        mgr = PortfolioStateManager()
        state = mgr.load()
        if 'cash' in data:
            if data['cash'] is None or float(data['cash']) < 0:
                return jsonify({'success': False, 'message': 'cash 必须非负'}), 400
            state.cash = float(data['cash'])
        if 'lot_size' in data and data['lot_size']:
            state.lot_size = int(data['lot_size'])
        if 'positions' in data and isinstance(data['positions'], dict):
            from src.portfolio.state import Position
            new_positions = {}
            for symbol, pdata in data['positions'].items():
                if not REGISTRY.is_registered(symbol):
                    return jsonify({'success': False,
                                    'message': f'未注册的股票: {symbol}'}), 400
                new_positions[symbol] = Position.from_dict(pdata)
            state.positions = new_positions
        saved = mgr.save(state)
        return jsonify({'success': True, 'state': saved.to_dict()})
    except (ValueError, KeyError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/portfolio_position', methods=['POST'])
def api_portfolio_position_set():
    """新增/更新单只持仓。"""
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol')
        if not symbol:
            return jsonify({'success': False, 'message': '缺少 symbol'}), 400
        shares = int(data.get('shares', 0))
        mgr = PortfolioStateManager()
        state = mgr.set_position(symbol, shares,
                                 avg_cost=data.get('avg_cost'),
                                 note=data.get('note'))
        return jsonify({'success': True, 'state': state.to_dict()})
    except (ValueError, KeyError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/portfolio_position', methods=['DELETE'])
def api_portfolio_position_delete():
    """移除单只持仓。"""
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol') or request.args.get('symbol')
        if not symbol:
            return jsonify({'success': False, 'message': '缺少 symbol'}), 400
        state = PortfolioStateManager().remove_position(symbol)
        return jsonify({'success': True, 'state': state.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/portfolio_risk_profile', methods=['GET'])
def api_portfolio_risk_get():
    """获取风险配置。"""
    try:
        profile = RiskProfileManager().load()
        return jsonify({'success': True, 'risk_profile': profile.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/portfolio_risk_profile', methods=['PUT'])
def api_portfolio_risk_put():
    """更新风险配置。"""
    try:
        data = request.get_json() or {}
        profile = RiskProfileManager().update(**data)
        return jsonify({'success': True, 'risk_profile': profile.to_dict()})
    except (ValueError, KeyError) as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/portfolio_decide', methods=['POST'])
def api_portfolio_decide():
    """组合级今日决策。"""
    try:
        data = request.get_json() or {}
        mode = data.get('mode', DecisionMode.CLOSE_AFTER_MARKET)
        symbols = data.get('symbols')
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(',') if s.strip()]
        quotes = data.get('quotes')
        open_prices = data.get('open_prices') or data.get('opens')

        engine = PortfolioDecisionEngine()
        result = engine.decide(mode, symbols=symbols,
                               quotes=quotes, open_prices=open_prices)
        return jsonify({'success': True, 'result': result})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# 基本面
# ============================================================

@app.route('/api/fundamental_records', methods=['GET'])
def api_fundamental_records():
    """获取所有股票基本面分析记录（只读）"""
    try:
        records = FundamentalRecords()
        return jsonify({
            'success': True,
            'records': records.list_all()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/fundamental_report', methods=['GET'])
def api_fundamental_report():
    """获取某股票最新基本面报告内容"""
    try:
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({'success': False, 'message': '缺少 symbol'}), 400
        records = FundamentalRecords()
        content = records.read_report(symbol)
        return jsonify({
            'success': True,
            'symbol': symbol,
            'has_report': content is not None,
            'content': content
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
