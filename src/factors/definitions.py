#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准因子定义

所有因子通过装饰器注册到 FACTOR_REGISTRY，供 Pipeline 配置引用。
"""

import pandas as pd
import numpy as np
from .registry import FACTOR_REGISTRY


@FACTOR_REGISTRY.register(
    name='sma',
    required_columns=['close'],
    default_params={'window': 20},
    description='简单移动平均'
)
def sma(df, window=20):
    return df['close'].rolling(window=window, min_periods=window).mean()


@FACTOR_REGISTRY.register(
    name='std',
    required_columns=['close'],
    default_params={'window': 20},
    description='滚动标准差'
)
def std(df, window=20):
    return df['close'].rolling(window=window, min_periods=window).std()


@FACTOR_REGISTRY.register(
    name='zscore',
    required_columns=['close'],
    default_params={'window': 20},
    description='收盘价偏离均线的标准差倍数 (close - ma) / std'
)
def zscore(df, window=20):
    ma = df['close'].rolling(window=window, min_periods=window).mean()
    s = df['close'].rolling(window=window, min_periods=window).std()
    return (df['close'] - ma) / s


@FACTOR_REGISTRY.register(
    name='slope',
    required_columns=['close'],
    default_params={'window': 20, 'period': 5},
    description='均线/价格在 period 周期内的平均变化率'
)
def slope(df, window=20, period=5):
    col = f'ma{window}' if f'ma{window}' in df.columns else 'close'
    return (df[col] - df[col].shift(period)) / period


@FACTOR_REGISTRY.register(
    name='returns',
    required_columns=['close'],
    default_params={'period': 5},
    description='period 周期收益率'
)
def returns(df, period=5):
    return df['close'].pct_change(period) * 100


@FACTOR_REGISTRY.register(
    name='golden_cross',
    required_columns=['close'],
    default_params={'fast': 20, 'slow': 60},
    description='快线是否大于慢线，0/1 指标'
)
def golden_cross(df, fast=20, slow=60):
    fast_col = f'ma{fast}' if f'ma{fast}' in df.columns else None
    slow_col = f'ma{slow}' if f'ma{slow}' in df.columns else None
    if fast_col and slow_col:
        return (df[fast_col] > df[slow_col]).astype(int)
    ma_fast = df['close'].rolling(window=fast, min_periods=fast).mean()
    ma_slow = df['close'].rolling(window=slow, min_periods=slow).mean()
    return (ma_fast > ma_slow).astype(int)


@FACTOR_REGISTRY.register(
    name='ma_gap',
    required_columns=['close'],
    default_params={'fast': 20, 'slow': 60},
    description='两条均线之间的差距百分比'
)
def ma_gap(df, fast=20, slow=60):
    fast_col = f'ma{fast}' if f'ma{fast}' in df.columns else None
    slow_col = f'ma{slow}' if f'ma{slow}' in df.columns else None
    if fast_col and slow_col:
        return (df[fast_col] / df[slow_col] - 1) * 100
    ma_fast = df['close'].rolling(window=fast, min_periods=fast).mean()
    ma_slow = df['close'].rolling(window=slow, min_periods=slow).mean()
    return (ma_fast / ma_slow - 1) * 100


@FACTOR_REGISTRY.register(
    name='volatility_ratio',
    required_columns=['close'],
    default_params={'window': 20},
    description='滚动标准差 / 滚动均值，即变异系数'
)
def volatility_ratio(df, window=20):
    return (
        df['close'].rolling(window=window, min_periods=window).std() /
        df['close'].rolling(window=window, min_periods=window).mean()
    )


@FACTOR_REGISTRY.register(
    name='macd',
    required_columns=['close'],
    default_params={'fast': 12, 'slow': 26, 'signal': 9},
    description='MACD 指标，返回 dict 包含 dif/dea/hist'
)
def macd(df, fast=12, slow=26, signal=9):
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = 2 * (dif - dea)
    return pd.DataFrame({'dif': dif, 'dea': dea, 'hist': hist})


@FACTOR_REGISTRY.register(
    name='rsi',
    required_columns=['close'],
    default_params={'window': 14},
    description='相对强弱指数 RSI'
)
def rsi(df, window=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window).mean()
    rs = avg_gain / avg_loss
    rsi_value = 100 - (100 / (1 + rs))
    return rsi_value


@FACTOR_REGISTRY.register(
    name='bollinger',
    required_columns=['close'],
    default_params={'window': 20, 'std_dev': 2},
    description='布林带，返回 dict 包含 upper/lower/mid'
)
def bollinger(df, window=20, std_dev=2):
    mid = df['close'].rolling(window=window, min_periods=window).mean()
    std = df['close'].rolling(window=window, min_periods=window).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return pd.DataFrame({'upper': upper, 'lower': lower, 'mid': mid})


@FACTOR_REGISTRY.register(
    name='rolling_tree_prob',
    required_columns=['close'],
    default_params={
        'feature_cols': ['ma20', 'z20', 'ret5', 'ret20', 'vol20'],
        'target_period': 1,
        'train_window': 126,
        'max_depth': 5,
        'min_train_samples': 10
    },
    description='滚动窗口决策树上涨概率特征（无未来信息）'
)
def rolling_tree_prob(df, feature_cols, target_period, train_window, max_depth, min_train_samples=10):
    """
    对每个时刻 i，用 [i-train_window, i) 数据训练决策树，
    预测第 i 时刻未来 target_period 期收盘价方向的概率。
    """
    from sklearn.tree import DecisionTreeClassifier

    target = (df['close'].shift(-target_period) > df['close']).astype(float)
    target[df['close'].shift(-target_period).isna()] = float('nan')
    probs = []

    for i in range(len(df)):
        train_df = df.iloc[max(0, i - train_window):i].copy()
        train_df['_target'] = target.iloc[max(0, i - train_window):i].values
        train_df = train_df.dropna(subset=feature_cols + ['_target'])
        if len(train_df) < min_train_samples:
            probs.append(0.5)
            continue
        X_train = train_df[feature_cols].values
        y_train = train_df['_target'].values
        X_test = df[feature_cols].iloc[i:i + 1].values

        dt = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
        dt.fit(X_train, y_train)
        prob = dt.predict_proba(X_test)[0][1]
        probs.append(prob)

    return pd.Series(probs, index=df.index)
