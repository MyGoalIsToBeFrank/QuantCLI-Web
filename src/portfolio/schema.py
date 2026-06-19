"""
组合层共享常量与决策模式定义

被 state / risk / quotes / modes / decision_engine / API / CLI 共享，
集中管理 lot_size、默认现金与三种决策模式，避免散落的魔法字符串。
"""

# A 股执行单位：每手 100 股，固定不变
DEFAULT_LOT_SIZE = 100

# 缺省账户初始现金（无状态文件时创建）
DEFAULT_CASH = 100000.0

# 状态/风险配置文件 schema 版本
SCHEMA_VERSION = 1


class DecisionMode:
    """组合决策模式。

    market timing 决定了哪些数据是合法可用的：
      - CLOSE_AFTER_MARKET：盘后，仅使用完整日线
      - OPEN_REALTIME：已知 T 日开盘价，不可窥视 T 日收/高/低
      - LATE_SESSION：尾盘，使用提供的行情快照，输出次日离场计划
    """

    CLOSE_AFTER_MARKET = 'close_after_market'
    OPEN_REALTIME = 'open_realtime'
    LATE_SESSION = 'late_session'

    ALL = [CLOSE_AFTER_MARKET, OPEN_REALTIME, LATE_SESSION]

    @classmethod
    def validate(cls, mode: str) -> str:
        if mode not in cls.ALL:
            raise ValueError(
                f'未知决策模式: {mode}；可选 {cls.ALL}'
            )
        return mode
