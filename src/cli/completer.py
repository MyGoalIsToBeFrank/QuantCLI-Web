"""
CLI 交互式补全工具

由于项目不依赖 prompt-toolkit，使用标准 input() 实现简单的
候选提示：用户输入部分代码后，列出匹配的股票供选择。
"""

import sys
from typing import List, Optional

from src.data.stock_registry import REGISTRY
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.cli.colors import header, subheader, dim, bold, success, warning, error


def _list_items(title: str, items: List[str], description_map=None):
    """带序号打印候选列表。"""
    print(subheader(title))
    for i, item in enumerate(items, 1):
        desc = ''
        if description_map:
            desc_info = description_map(item)
            if desc_info:
                desc = f'  {dim(desc_info)}'
        print(f'  {bold(f"[{i}]")} {item}{desc}')
    print()


def _prompt_choice(prompt_text: str, items: List[str]) -> Optional[str]:
    """
    提示用户从 items 中选择一个。
    支持输入序号或完整名称；输入空行或 q 返回 None。
    """
    while True:
        try:
            raw = input(dim(prompt_text)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if not raw or raw.lower() in ('q', 'quit', 'exit'):
            return None

        # 序号选择
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print(warning(f'序号无效，请输入 1~{len(items)} 之间的数字'))
            continue

        # 精确匹配
        if raw in items:
            return raw

        # 部分匹配
        matches = [x for x in items if raw.upper() in x.upper()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print(warning(f'"{raw}" 匹配到多个候选：'))
            for m in matches:
                print(f'  - {m}')
            continue

        print(error(f'未找到匹配 "{raw}" 的选项，请重新输入'))


def prompt_symbol(allow_multiple: bool = False) -> List[str]:
    """
    交互式选择股票代码。

    allow_multiple=True 时允许选择多个，输入空行结束。
    """
    symbols = REGISTRY.list_symbols()
    if not symbols:
        print(error('股票注册表为空'))
        return []

    print(header('\n股票代码选择'))
    _list_items(
        '可用股票：',
        symbols,
        description_map=lambda s: REGISTRY.get(s).name if REGISTRY.get(s) else ''
    )

    if allow_multiple:
        print(dim('提示：输入序号或代码，空行结束选择'))
        selected = []
        while True:
            raw = input(dim(f'选择第 {len(selected) + 1} 只股票（空行结束）：')).strip()
            if not raw:
                break
            choice = _resolve_choice(raw, symbols)
            if choice:
                selected.append(choice)
                print(success(f'  已选择 {choice}'))
        return selected

    choice = _prompt_choice('请输入股票代码或序号：', symbols)
    return [choice] if choice else []


def _resolve_choice(raw: str, items: List[str]) -> Optional[str]:
    """把用户输入解析为 items 中的一项。"""
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(items):
            return items[idx]
        return None
    if raw in items:
        return raw
    matches = [x for x in items if raw.upper() in x.upper()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(warning(f'"{raw}" 匹配到多个候选：{", ".join(matches)}'))
    else:
        print(error(f'未找到匹配 "{raw}" 的选项'))
    return None


def resolve_symbols(args_symbols,
                    allow_multiple: bool = True,
                    prompt_if_empty: bool = True) -> List[str]:
    """
    解析命令行传入的股票代码。

    - 若已传入（字符串或列表），直接返回列表。
    - 若未传入且 prompt_if_empty=True，进入交互选择。
    """
    if args_symbols:
        if isinstance(args_symbols, str):
            return [args_symbols]
        return list(args_symbols)

    if not prompt_if_empty:
        return []

    return prompt_symbol(allow_multiple=allow_multiple)


def prompt_component(kind: str) -> Optional[str]:
    """
    交互式选择 Pipeline 或 Strategy。
    """
    if kind == 'pipeline':
        items = PIPELINE_REGISTRY.list_names()
        title = '可用 Pipeline：'
    elif kind == 'strategy':
        items = STRATEGY_REGISTRY.list_names()
        title = '可用 Strategy：'
    else:
        raise ValueError(f'不支持的组件类型：{kind}')

    if not items:
        print(error(f'{kind} 注册表为空'))
        return None

    print(header(f'\n{kind.title()} 选择'))
    _list_items(title, items)
    return _prompt_choice(f'请输入 {kind} 名称或序号：', items)


def resolve_backtest_args(args) -> Optional[tuple]:
    """
    交互式解析 backtest 所需的 symbol / pipeline / strategy。
    返回 (symbol, pipeline, strategy) 或 None（用户取消）。
    """
    symbols = resolve_symbols(getattr(args, 'symbol', None), allow_multiple=False)
    if not symbols:
        return None
    symbol = symbols[0]

    pipeline = getattr(args, 'pipeline', None)
    if not pipeline:
        pipeline = prompt_component('pipeline')
        if not pipeline:
            return None

    strategy = getattr(args, 'strategy', None)
    if not strategy:
        strategy = prompt_component('strategy')
        if not strategy:
            return None

    return symbol, pipeline, strategy
