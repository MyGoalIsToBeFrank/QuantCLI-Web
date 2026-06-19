#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一 CLI 入口

支持两种调用方式：
  1. 通过主入口调用：strategy analyze 002156.SZ
  2. 通过同名包装脚本调用：analyze 002156.SZ

包装脚本只需把调用转发给 strategy，本文件会根据 sys.argv[0]
自动推断默认子命令。
"""

import sys
import os
import io
import shlex

# 强制 CLI 输出使用 UTF-8，避免 Windows 终端默认 GBK 导致的中文乱码。
# 仅在真实终端下重包装 stdout/stderr；在 pytest 捕获/重定向场景下跳过，
# 否则会包装并持有随后被关闭的捕获缓冲区，触发 "I/O operation on closed file"。
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer') and sys.stdout.isatty():
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .commands import (
    data_cmd, analyze_cmd, scan_cmd, backtest_cmd,
    decide_cmd, list_cmd, fundamental_cmd, chart_cmd, help_cmd,
    portfolio_cmd
)
from .colors import header, subheader, dim, bold



COMMANDS = [
    'data', 'analyze', 'scan', 'backtest', 'decide',
    'list', 'fundamental', 'chart', 'help', 'portfolio'
]


def _normalize_argv():
    """
    若程序通过 analyze.bat / analyze 等包装脚本启动，
    则把子命令名插入到 argv 中，使其等价于 `strategy analyze ...`
    """
    invoked = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    if invoked in COMMANDS:
        sys.argv = [sys.argv[0]] + [invoked] + sys.argv[1:]


def _print_prompt():
    print(header('量化策略 CLI'))
    print()
    print(subheader('常用命令：'))
    print(f'  {bold("analyze")} [SYMBOL ...]              季度策略分析')
    print(f'  {bold("scan")} [SYMBOL ...]                 全区间扫描最佳组合')
    print(f'  {bold("backtest")} SYMBOL PIPELINE STRATEGY 单一组合回测')
    print(f'  {bold("decide")} [SYMBOL ...]               今日决策')
    print(f'  {bold("portfolio")} {{show,set-cash,set-position,decide,risk-profile}} 组合决策')
    print(f'  {bold("chart")} SYMBOL                      终端 ASCII K 线图')
    print(f'  {bold("list")} {{pipelines,strategies,stocks}} 列出可用组件')
    print(f'  {bold("data")} {{list,update [SYMBOL],info [SYMBOL]}} 数据管理')
    print(f'  {bold("fundamental")} {{check,prompt,report,list,show}} SYMBOL 基本面分析')
    print(f'  {bold("help")} [COMMAND]                  显示帮助信息')
    print()
    print(dim('提示：可直接运行 QuantCLI.bat analyze 002156.SZ，无需输入 strategy 前缀。'))
    print(dim('直接运行 QuantCLI.bat 可进入 QuantCLI> 交互模式。'))
    print(dim('详细帮助：QuantCLI.bat --help 或 QuantCLI.bat help <命令>'))


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog='strategy',
        description='量化策略 CLI：多股票、多 Pipeline、多策略回测与决策'
    )
    parser.add_argument('--no-color', action='store_true',
                        help='禁用 ANSI 颜色输出')
    subparsers = parser.add_subparsers(dest='command')

    data_cmd.register(subparsers)
    analyze_cmd.register(subparsers)
    scan_cmd.register(subparsers)
    backtest_cmd.register(subparsers)
    decide_cmd.register(subparsers)
    list_cmd.register(subparsers)
    fundamental_cmd.register(subparsers)
    chart_cmd.register(subparsers)
    portfolio_cmd.register(subparsers)
    help_cmd.register(subparsers)
    return parser


def _prepare_argv(argv):
    argv = list(argv)
    # 提前检查 --no-color，以便后续命令保持兼容；保留 parser 参数用于 --help 展示。
    if '--no-color' in argv:
        os.environ['NO_COLOR'] = '1'
        argv.remove('--no-color')
    return argv


def _run_command(argv, parser):
    args = parser.parse_args(_prepare_argv(argv))
    if not getattr(args, 'command', None) and not getattr(args, 'func', None):
        _print_prompt()
        return
    args.func(args)


def _interactive_loop():
    print(header('QuantCLI 交互模式'))
    print(dim('输入 help 查看命令，输入 exit 或 quit 退出。'))
    print()

    while True:
        try:
            line = input('QuantCLI> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        if line.lower() in {'exit', 'quit'}:
            break

        try:
            argv = shlex.split(line)
        except ValueError as exc:
            print(f'命令解析错误：{exc}')
            continue

        try:
            _run_command(argv, _build_parser())
        except SystemExit as exc:
            if exc.code not in (0, None):
                print(dim(f'命令退出码：{exc.code}'))

    print('已退出 QuantCLI')


def main():
    _normalize_argv()

    parser = _build_parser()
    argv = _prepare_argv(sys.argv[1:])
    if not argv:
        if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
            _interactive_loop()
        else:
            _print_prompt()
        return

    args = parser.parse_args(argv)
    if not getattr(args, 'command', None) and not getattr(args, 'func', None):
        _print_prompt()
        return
    args.func(args)


if __name__ == '__main__':
    main()
