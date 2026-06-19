#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准监督目标定义

所有目标通过装饰器注册到 TARGET_REGISTRY，供 Pipeline 配置引用。
"""

from .target_registry import TARGET_REGISTRY


@TARGET_REGISTRY.register(
    name='ma_direction',
    required_columns=['close'],
    default_params={'window': 5},
    description='未来 window 期后均线是否高于当前'
)
def ma_direction(df, window=5):
    ma = df['close'].rolling(window=window, min_periods=window).mean()
    future_ma = ma.shift(-window)
    target = (future_ma > ma).astype(float)
    target[future_ma.isna() | ma.isna()] = float('nan')
    return target


@TARGET_REGISTRY.register(
    name='price_direction',
    required_columns=['close'],
    default_params={'period': 1},
    description='未来 period 期后收盘价是否高于当前'
)
def price_direction(df, period=1):
    future_close = df['close'].shift(-period)
    target = (future_close > df['close']).astype(float)
    target[future_close.isna()] = float('nan')
    return target


@TARGET_REGISTRY.register(
    name='return_bucket',
    required_columns=['close'],
    default_params={'period': 5, 'threshold': 0.0},
    description='未来 period 期收益率是否超过 threshold'
)
def return_bucket(df, period=5, threshold=0.0):
    future_ret = df['close'].shift(-period) / df['close'] - 1
    target = (future_ret > threshold).astype(float)
    target[future_ret.isna()] = float('nan')
    return target


@TARGET_REGISTRY.register(
    name='volatility_breakout',
    required_columns=['close'],
    default_params={'window': 20, 'period': 5, 'threshold': 0.02},
    description='未来 period 期真实波动率是否超过 threshold'
)
def volatility_breakout(df, window=20, period=5, threshold=0.02):
    returns = df['close'].pct_change()
    past_vol = returns.rolling(window=window).std()
    future_vol = returns.shift(-period).rolling(window=period).std()
    ratio = future_vol / past_vol
    target = (ratio > threshold).astype(float)
    target[ratio.isna() | returns.shift(-period).isna()] = float('nan')
    return target
