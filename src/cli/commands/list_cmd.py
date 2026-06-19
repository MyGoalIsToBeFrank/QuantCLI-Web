"""
list 命令：列出可用组件

用法：
    strategy list {pipelines,strategies,stocks}
"""

from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.data.stock_registry import REGISTRY
from src.cli.colors import header, bold


def register(subparsers):
    p = subparsers.add_parser('list', help='列出可用组件')
    p.add_argument('target', nargs='?', default='pipelines',
                   choices=['pipelines', 'strategies', 'stocks'],
                   help='列出对象（默认 pipelines）')
    p.set_defaults(func=handle)


def handle(args):
    if args.target == 'pipelines':
        print(header('可用 Pipeline：'))
        for info in PIPELINE_REGISTRY.list_info():
            print(f"  {bold(info['name'])}")
            print(f"    输入列：{info['required_columns']}")
            print(f"    输出键：{info['output_keys']}")

    elif args.target == 'strategies':
        print(header('可用 Strategy：'))
        for info in STRATEGY_REGISTRY.list_info():
            print(f"  {bold(info['name'])}")
            print(f"    依赖键：{info['accepted_keys']}")

    elif args.target == 'stocks':
        print(header('股票池：'))
        for info in REGISTRY.list_all():
            print(f"  {bold(info.symbol)} {info.name} ({info.market}) [{info.sector or 'N/A'}]")
