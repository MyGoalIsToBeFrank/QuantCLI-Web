"""
help 命令：显示全局或指定子命令的帮助信息。

用法：
    strategy help
    strategy help analyze
    strategy help backtest
"""

import sys

from src.cli.colors import header, subheader, bold, dim


# 各命令的简要说明与示例
_COMMANDS_INFO = {
    'analyze': {
        'desc': '季度策略分析：按季度滚动回测所有 (Pipeline, Strategy) 组合。',
        'examples': [
            'QuantCLI.bat analyze 002156.SZ --start 2024-06-01 --end 2026-06-17 --save',
            'QuantCLI.bat analyze --max-drawdown 5 --save',
        ]
    },
    'scan': {
        'desc': '全区间扫描最佳组合：在所有 Pipeline × Strategy 中选出最优者。',
        'examples': [
            'QuantCLI.bat scan 002156.SZ --start 2025-12-18 --end 2026-06-17 --save',
            'QuantCLI.bat scan --max-drawdown 5 --save',
        ]
    },
    'backtest': {
        'desc': '单一组合回测：对指定的 (股票, Pipeline, Strategy) 进行回测。',
        'examples': [
            'QuantCLI.bat backtest 002156.SZ ma_dual prob_position --start 2025-12-18 --end 2026-06-17',
            'QuantCLI.bat backtest            # 交互式选择',
        ]
    },
    'decide': {
        'desc': '今日决策：基于已保存的最佳组合给出当前交易日操作建议。',
        'examples': [
            'QuantCLI.bat decide 002156.SZ --open 68.0',
            'QuantCLI.bat decide              # 交互式选择',
        ]
    },
    'chart': {
        'desc': '终端 ASCII K 线图：在命令行中绘制 K 线与均线。',
        'examples': [
            'QuantCLI.bat chart 002156.SZ --ma 5,20 --height 20',
            'QuantCLI.bat chart               # 交互式选择',
        ]
    },
    'list': {
        'desc': '列出可用组件：pipelines / strategies / stocks。',
        'examples': [
            'QuantCLI.bat list pipelines',
            'QuantCLI.bat list stocks',
        ]
    },
    'data': {
        'desc': '数据管理：查看股票列表、更新单只或全部股票数据。',
        'examples': [
            'QuantCLI.bat data list',
            'QuantCLI.bat data update 002156.SZ',
            'QuantCLI.bat data update',
        ]
    },
    'fundamental': {
        'desc': '基本面分析与 Agent 协作：检查、生成 prompt、写回报告。',
        'examples': [
            'QuantCLI.bat fundamental check 002156.SZ',
            'QuantCLI.bat fundamental prompt 002156.SZ',
            'QuantCLI.bat fundamental list',
        ]
    },
    'help': {
        'desc': '显示帮助信息。',
        'examples': [
            'QuantCLI.bat help',
            'QuantCLI.bat help backtest',
        ]
    },
}


def register(subparsers):
    p = subparsers.add_parser('help', help='显示帮助信息')
    p.add_argument('command', nargs='?', help='要查看帮助的子命令名')
    p.set_defaults(func=handle)


def handle(args):
    if args.command:
        _print_command_help(args.command)
    else:
        _print_global_help()


def _print_global_help():
    print(header('量化策略 CLI 帮助'))
    print()
    print(subheader('可用命令：'))
    for name, info in _COMMANDS_INFO.items():
        print(f'  {bold(name):<12} {info["desc"]}')
    print()
    print(subheader('快速入口：'))
    print(f'  {bold("QuantCLI.bat")}         显示常用命令提示')
    print(f'  {bold("QuantWebUI.bat")}       启动 Web UI')
    print()
    print(dim('提示：使用 "QuantCLI.bat help <命令>" 查看具体命令用法与示例。'))


def _print_command_help(command: str):
    info = _COMMANDS_INFO.get(command)
    if not info:
        print(f'未知命令：{command}')
        print(dim('可用命令：' + ', '.join(_COMMANDS_INFO.keys())))
        sys.exit(2)

    print(header(f'命令帮助：{bold(command)}'))
    print()
    print(info['desc'])
    print()
    print(subheader('示例：'))
    for ex in info['examples']:
        print(f'  {ex}')
    print()
    print(dim(f'提示：使用 "QuantCLI.bat {command} --help" 查看完整参数列表。'))
