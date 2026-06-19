"""
预测 Pipeline 基类

Pipeline 职责：输入单只股票 raw_df，输出预测信号/分数。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import pandas as pd


class BasePipeline(ABC):
    """
    所有预测管线的基类。

    子类必须实现：
      - name: 类属性，唯一名称
      - required_columns: 输入 raw_df 必须包含的列
      - output_keys: predict() 返回字典中包含的键
      - fit(raw_df, end_idx=None): 训练/拟合
      - predict(idx=None) -> dict: 对第 idx 行预测

    典型 predict 输出键：
      - 'score': float，[-1, 1] 区间，>0 偏多，<0 偏空
      - 'prob_bull': float，[0, 1]，上涨概率
      - 'signal': str，'bull' / 'bear' / 'neutral'
      - 'metadata': dict，额外信息（如 RSI 值、MACD 值等）
    """

    name: str = 'base'

    @property
    @abstractmethod
    def required_columns(self) -> List[str]:
        """输入 DataFrame 必须包含的列"""
        pass

    @property
    @abstractmethod
    def output_keys(self) -> List[str]:
        """predict() 返回的字典至少包含这些键"""
        pass

    def validate(self, raw_df: pd.DataFrame) -> None:
        missing = [c for c in self.required_columns if c not in raw_df.columns]
        if missing:
            raise ValueError(f'{self.name} 缺少列: {missing}')

    @abstractmethod
    def fit(self, raw_df: pd.DataFrame, end_idx: int = None) -> None:
        """
        拟合/训练 pipeline。

        参数:
            raw_df: 单只股票 OHLCV 数据
            end_idx: 若指定，只使用 [0:end_idx) 数据训练
        """
        pass

    @abstractmethod
    def predict(self, idx: int = None) -> Dict[str, Any]:
        """
        预测第 idx 行；默认最后一行。

        返回 dict 至少包含 output_keys 中声明的键。
        """
        pass

    def fit_predict(self, raw_df: pd.DataFrame, end_idx: int = None,
                    idx: int = None) -> Dict[str, Any]:
        """便捷方法：fit + predict"""
        self.fit(raw_df, end_idx=end_idx)
        return self.predict(idx=idx)
