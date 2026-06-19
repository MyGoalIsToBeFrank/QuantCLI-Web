"""
CLI 彩色输出工具

参考 codex-cli 风格：
  - 标题：亮蓝/加粗
  - 成功：绿色
  - 警告：黄色
  - 错误：红色
  - 指标：正数绿色、负数红色、大额回撤红色

Windows Git Bash 与主流终端均支持 ANSI 转义码；
如检测到不支持 ANSI 的终端，会自动禁用颜色。
"""

import os
import sys


# 可选：在 Windows cmd/powershell 中把 ANSI 转义码转换为控制台 API 调用
# 仅在交互式终端启用转换；重定向/管道时保留原始 ANSI 转义码
try:
    import colorama
    # 仅在真实终端启用 colorama 包装，避免在重定向/管道/pytest 捕获下
    # 包装并持有已被关闭的输出流（会导致 "I/O operation on closed file"）。
    if getattr(sys.stdout, 'isatty', lambda: False)():
        colorama.init(strip=False, convert=True)
except Exception:
    pass


# 检测是否支持颜色
_FORCE_COLOR = os.environ.get('FORCE_COLOR', '')
_NO_COLOR = os.environ.get('NO_COLOR', '')


def _supports_color() -> bool:
    """粗略判断终端是否支持 ANSI 颜色"""
    if _FORCE_COLOR:
        return True
    if _NO_COLOR:
        return False
    # 非 TTY 不启用颜色（重定向到文件时）
    if not sys.stdout.isatty():
        return False
    return True


_SUPPORTS_COLOR = _supports_color()


class _Styles:
    """ANSI 转义码定义"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'

    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'

    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'


def _apply(text: str, *codes: str) -> str:
    if not _SUPPORTS_COLOR:
        return text
    return ''.join(codes) + str(text) + _Styles.RESET


def header(text: str) -> str:
    """大标题：亮蓝加粗"""
    return _apply(text, _Styles.BOLD, _Styles.BRIGHT_BLUE)


def subheader(text: str) -> str:
    """小标题：青色加粗"""
    return _apply(text, _Styles.BOLD, _Styles.BRIGHT_CYAN)


def success(text: str) -> str:
    """成功信息：绿色"""
    return _apply(text, _Styles.BRIGHT_GREEN)


def warning(text: str) -> str:
    """警告信息：黄色"""
    return _apply(text, _Styles.BRIGHT_YELLOW)


def error(text: str) -> str:
    """错误信息：红色"""
    return _apply(text, _Styles.BRIGHT_RED)


def dim(text: str) -> str:
    """次要信息：暗淡"""
    return _apply(text, _Styles.DIM)


def bold(text: str) -> str:
    """加粗"""
    return _apply(text, _Styles.BOLD)


def value_positive(text: str) -> str:
    """正数/利好：绿色"""
    return _apply(text, _Styles.BRIGHT_GREEN)


def value_negative(text: str) -> str:
    """负数/利空：红色"""
    return _apply(text, _Styles.BRIGHT_RED)


def metric(text: str, value: float,
           good_if_greater_than: float = None,
           bad_if_less_than: float = None,
           reverse: bool = False) -> str:
    """
    根据数值自动着色。

    reverse=True 时，数值越小越好（如最大回撤）。
    """
    if reverse:
        if bad_if_less_than is not None and value < bad_if_less_than:
            return value_negative(text)
        if good_if_greater_than is not None and value > good_if_greater_than:
            return value_negative(text)
        return value_positive(text)

    if good_if_greater_than is not None and value > good_if_greater_than:
        return value_positive(text)
    if bad_if_less_than is not None and value < bad_if_less_than:
        return value_negative(text)
    return text


def return_pct(value: float) -> str:
    """收益率着色：正绿负红"""
    text = f'{value:+.2f}%'
    return value_positive(text) if value >= 0 else value_negative(text)


def drawdown_pct(value: float, threshold: float = 5.0) -> str:
    """回撤着色：超过阈值标红，否则绿色/黄色"""
    text = f'{value:.2f}%'
    if value <= -threshold:
        return value_negative(text)
    if value <= -threshold * 0.6:
        return warning(text)
    return value_positive(text)


def print_header(text: str):
    print(header(text))


def print_success(text: str):
    print(success(text))


def print_warning(text: str):
    print(warning(text))


def print_error(text: str):
    print(error(text))
