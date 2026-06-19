"""
fundamental 命令：基本面分析与 AI Agent 协作接口

用法：
    strategy fundamental check SYMBOL
    strategy fundamental prompt SYMBOL
    strategy fundamental report SYMBOL -f FILE
    strategy fundamental list
    strategy fundamental show SYMBOL
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from src.fundamental.records import FundamentalRecords
from src.cli.colors import (
    header, success, warning, error, bold, dim
)
from src.cli.completer import resolve_symbols


def _skill_path():
    """
    基本面分析 SKILL 文件路径。

    优先从环境变量 `STOCK_BASIC_ANALYSIS_SKILL` 读取；
    未设置时尝试项目内默认位置 `.agents/skills/stock-basic-analysis/SKILL.md`。
    """
    env = os.environ.get('STOCK_BASIC_ANALYSIS_SKILL')
    if env:
        return Path(env)
    return Path('.agents/skills/stock-basic-analysis/SKILL.md')


def register(subparsers):
    p = subparsers.add_parser('fundamental', help='基本面分析与 Agent 协作')
    sub = p.add_subparsers(dest='fundamental_action', required=True)

    p_check = sub.add_parser('check', help='检查是否需要进行基本面分析')
    p_check.add_argument('symbol', nargs='?', help='股票代码；省略进入交互选择')
    p_check.add_argument('--interval', '-i', type=int, default=30,
                         help='分析间隔天数（默认 30）')
    p_check.set_defaults(func=handle_check)

    p_prompt = sub.add_parser('prompt', help='输出发给 AI Agent 的 prompt')
    p_prompt.add_argument('symbol', nargs='?', help='股票代码；省略进入交互选择')
    p_prompt.add_argument('--interval', '-i', type=int, default=30,
                          help='分析间隔天数（默认 30）')
    p_prompt.set_defaults(func=handle_prompt)

    p_report = sub.add_parser('report', help='写回 Agent 生成的基本面分析报告')
    p_report.add_argument('symbol', nargs='?', help='股票代码；省略进入交互选择')
    p_report.add_argument('--file', '-f', required=True, help='报告文件路径')
    p_report.add_argument('--interval', '-i', type=int, default=30,
                          help='分析间隔天数（默认 30）')
    p_report.set_defaults(func=handle_report)

    p_list = sub.add_parser('list', help='列出所有股票的基本面分析记录')
    p_list.add_argument('--interval', '-i', type=int, default=30,
                        help='分析间隔天数（默认 30）')
    p_list.set_defaults(func=handle_list)

    p_show = sub.add_parser('show', help='查看某股票最新报告')
    p_show.add_argument('symbol', nargs='?', help='股票代码；省略进入交互选择')
    p_show.add_argument('--interval', '-i', type=int, default=30,
                        help='分析间隔天数（默认 30）')
    p_show.set_defaults(func=handle_show)


def _records(interval_days):
    return FundamentalRecords(interval_days=interval_days)


def _resolve_symbol(args):
    """解析 symbol，未提供时进入交互选择。"""
    if args.symbol:
        return args.symbol
    symbols = resolve_symbols([], allow_multiple=False)
    return symbols[0] if symbols else None


def handle_check(args):
    symbol = _resolve_symbol(args)
    if not symbol:
        return
    records = _records(args.interval)
    try:
        result = records.check(symbol)
    except ValueError as e:
        print(error(f'错误：{e}'))
        sys.exit(2)

    print(header(f"股票：{result['symbol']} {result['name']}"))
    print(f"上次分析：{result['last_analysis_date'] or '从未分析'}")
    print(f"建议下次：{result['next_due_date']}")
    print(f"距离到期：{result['days_until_due']} 天")
    status = warning('是') if result['is_needed'] else success('否')
    print(f"是否需要分析：{status}")
    sys.exit(0 if result['is_needed'] else 1)


def handle_prompt(args):
    symbol = _resolve_symbol(args)
    if not symbol:
        return
    records = _records(args.interval)
    try:
        result = records.check(symbol)
    except ValueError as e:
        print(error(f'错误：{e}'))
        sys.exit(2)

    name = result['name']
    last_date = result['last_analysis_date'] or '从未分析'

    skill_path = _skill_path()
    skill_hint = ''
    if skill_path.exists():
        skill_hint = f'参考 SKILL 文件：{skill_path}'
    else:
        skill_hint = (
            '未找到外部 SKILL 文件。\n'
            '可通过环境变量 STOCK_BASIC_ANALYSIS_SKILL 指定，\n'
            '或将 SKILL.md 放到 .agents/skills/stock-basic-analysis/SKILL.md。'
        )

    prompt = f"""你好，agent！

请对 **{symbol} {name}** 进行基本面分析。

{skill_hint}

该 SKILL 通常涵盖数据获取、四维度打分（盈利能力、成长性、财务健康、估值）、技术面分析、趋势提取、多因子预测、异常波动检测及报告生成等完整流程。请根据当前可获取的数据，执行你认为必要的分析步骤，并生成一份结构化的 Markdown 基本面分析报告。

当前记录：
  - 股票代码：{symbol}
  - 股票名称：{name}
  - 上次分析日期：{last_date}
  - 建议分析间隔：每 {args.interval} 天一次

完成后，如需将报告写回系统记录，请使用以下 CLI 命令：

  strategy fundamental report {symbol} -f <你的报告文件路径>

报告建议包含：核心业务概述、四维度评分与评级、关键财务指标、技术面摘要、趋势与预测、风险提示及投资建议。
"""
    print(prompt)


def handle_report(args):
    symbol = _resolve_symbol(args)
    if not symbol:
        return
    records = _records(args.interval)
    try:
        summary = records.write_report(symbol, args.file)
    except (ValueError, FileNotFoundError) as e:
        print(error(f'错误：{e}'))
        sys.exit(2)

    print(success(f"已写回 {bold(summary['symbol'])} {summary['name']} 的基本面分析报告"))
    print(f"分析日期：{summary['last_analysis_date']}")
    print(f"归档路径：{summary['report_path']}")


def handle_list(args):
    records = _records(args.interval)
    results = records.list_all()

    if not results:
        print(warning('股票注册表为空'))
        return

    print(header(f"{'代码':<12} {'名称':<12} {'上次分析':<14} {'建议下次':<14} {'状态':<8}"))
    print(dim('-' * 70))
    for r in results:
        status = warning('需要') if r['is_needed'] else success('无需')
        last = r['last_analysis_date'] or '从未分析'
        print(f"{bold(r['symbol']):<12} {r['name']:<12} {last:<14} {r['next_due_date']:<14} {status:<8}")


def handle_show(args):
    symbol = _resolve_symbol(args)
    if not symbol:
        return
    records = _records(args.interval)
    try:
        content = records.read_report(symbol)
    except ValueError as e:
        print(error(f'错误：{e}'))
        sys.exit(2)

    if content is None:
        print(warning(f"{symbol} 暂无已归档的基本面分析报告"))
        return

    print(content)
