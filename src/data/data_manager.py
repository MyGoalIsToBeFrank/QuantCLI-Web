"""
多股票数据管理器

职责：
  1. 加载单只股票 CSV（统一列名：date, open, high, low, close, volume）。
  2. 从 Yahoo Finance 增量更新单只股票数据。
  3. 管理 data/stocks/ 目录。

接口契约（单只股票 raw_df）：
    columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    date 为 date 类型或 ISO 字符串
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yyf

from .stock_registry import StockRegistry, REGISTRY


# 单只股票 CSV 标准列
STOCK_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']
OPTIONAL_COLUMNS = ['adj_close']


def _csv_path(symbol: str, data_dir: Path = None) -> Path:
    if data_dir is None:
        data_dir = Path('data')
    return data_dir / 'stocks' / f'{symbol}.csv'


def load_stock(symbol: str, data_dir: Path = None,
               registry: StockRegistry = REGISTRY) -> pd.DataFrame:
    """
    加载单只股票历史数据。

    返回:
        DataFrame，列名为 ['date', 'open', 'high', 'low', 'close', 'volume']
    """
    if not registry.is_registered(symbol):
        raise ValueError(f'股票 {symbol} 未在 stock_registry 中注册')

    path = _csv_path(symbol, data_dir)
    if not path.exists():
        raise FileNotFoundError(f'找不到 {symbol} 数据文件: {path}')

    df = pd.read_csv(path)
    # 兼容大小写
    df.columns = [c.lower() for c in df.columns]

    # 统一列名
    rename_map = {}
    if 'time' in df.columns:
        rename_map['time'] = 'date'
    if 'datetime' in df.columns:
        rename_map['datetime'] = 'date'
    if rename_map:
        df = df.rename(columns=rename_map)

    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.date
    df = df.sort_values('date').reset_index(drop=True)

    # 确保包含标准列
    for col in STOCK_COLUMNS:
        if col not in df.columns:
            raise ValueError(f'{symbol} 数据缺少列 {col}')

    output_columns = STOCK_COLUMNS + [c for c in OPTIONAL_COLUMNS if c in df.columns]
    return df[output_columns]


def _download_yfinance(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """从 yfinance 下载股票数据并统一列名"""
    try:
        df = yyf.download(symbol, start=start, end=end, progress=False, auto_adjust=False)
        if df.empty:
            return None
        df = df.reset_index()

        # 处理多级列名（yfinance 返回 MultiIndex）
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df.columns = [str(c).lower().strip() for c in df.columns]

        rename = {}
        for c in df.columns:
            if c == 'date':
                rename[c] = 'date'
            elif c in ['open', 'high', 'low', 'close', 'volume', 'adj close']:
                rename[c] = c

        df = df.rename(columns=rename)

        if 'adj close' in df.columns:
            df['adj_close'] = df['adj close']

        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.date
        output_columns = STOCK_COLUMNS + [c for c in OPTIONAL_COLUMNS if c in df.columns]
        df = df[output_columns]
        df = df.dropna()
        return df
    except Exception as e:
        print(f'[DataManager] 下载 {symbol} 失败: {e}')
        return None


def update_stock(symbol: str, data_dir: Path = None,
                 registry: StockRegistry = REGISTRY) -> dict:
    """
    增量更新单只股票数据。

    返回:
        {'success': bool, 'message': str, 'rows': int}
    """
    if not registry.is_registered(symbol):
        return {'success': False, 'message': f'股票 {symbol} 未注册', 'rows': 0}

    info = registry.get(symbol)
    path = _csv_path(symbol, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 加载现有数据或创建空表
    if path.exists():
        existing = pd.read_csv(path)
        existing.columns = [c.lower() for c in existing.columns]
        if 'time' in existing.columns:
            existing = existing.rename(columns={'time': 'date'})
        existing['date'] = pd.to_datetime(existing['date']).dt.tz_localize(None).dt.date
    else:
        existing = pd.DataFrame(columns=STOCK_COLUMNS)

    today = datetime.now().date()
    # 首次下载拉取 5 年历史；后续增量更新拉取最近 30 天
    lookback_days = 30 if len(existing) > 0 else 1825
    start = (today - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    end = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    new_df = _download_yfinance(info.yf_symbol or symbol, start, end)
    if new_df is None or new_df.empty:
        rows = len(existing)
        existing = existing.sort_values('date').reset_index(drop=True)
        output_columns = STOCK_COLUMNS + [c for c in OPTIONAL_COLUMNS if c in existing.columns]
        existing[output_columns].to_csv(path, index=False)
        return {'success': True,
                'message': f'{symbol} 无新数据（最新 {existing["date"].max() if rows else "无"}）',
                'rows': rows}

    merged = pd.concat([existing, new_df], ignore_index=True)
    merged = merged.drop_duplicates(subset=['date'], keep='last')
    merged = merged.sort_values('date').reset_index(drop=True)
    output_columns = STOCK_COLUMNS + [c for c in OPTIONAL_COLUMNS if c in merged.columns]
    merged[output_columns].to_csv(path, index=False)

    return {'success': True,
            'message': f'{symbol} 更新至 {merged["date"].max()}，共 {len(merged)} 条',
            'rows': len(merged)}


def list_stock_files(data_dir: Path = None) -> list:
    """返回 data/stocks/ 下所有 CSV 文件名"""
    if data_dir is None:
        data_dir = Path('data')
    stocks_dir = data_dir / 'stocks'
    if not stocks_dir.exists():
        return []
    return [f for f in stocks_dir.iterdir() if f.is_file() and f.suffix == '.csv']


def verify_stock_data(symbol: str, days: int = 3,
                      data_dir: Path = None,
                      registry: StockRegistry = REGISTRY) -> dict:
    """Compare recent local OHLCV data with yfinance without writing files."""
    if not registry.is_registered(symbol):
        return {'success': False, 'symbol': symbol, 'message': f'{symbol} is not registered'}

    try:
        local = load_stock(symbol, data_dir=data_dir, registry=registry)
    except Exception as e:
        return {'success': False, 'symbol': symbol, 'message': f'local load failed: {e}'}

    info = registry.get(symbol)
    end = datetime.now().date() + timedelta(days=1)
    start = end - timedelta(days=max(days * 3, 10))
    remote = _download_yfinance(
        info.yf_symbol or symbol,
        start.strftime('%Y-%m-%d'),
        end.strftime('%Y-%m-%d')
    )
    if remote is None or remote.empty:
        return {'success': False, 'symbol': symbol, 'message': 'download failed or returned no rows'}

    local_recent = local.tail(days).copy()
    remote_recent = remote[remote['date'].isin(local_recent['date'])].copy()
    if remote_recent.empty:
        return {'success': False, 'symbol': symbol, 'message': 'no overlapping remote rows'}

    merged = local_recent.merge(remote_recent, on='date', suffixes=('_local', '_remote'))
    mismatches = []
    for _, row in merged.iterrows():
        for col in ['open', 'high', 'low', 'close', 'volume']:
            local_value = float(row[f'{col}_local'])
            remote_value = float(row[f'{col}_remote'])
            tolerance = 1e-4 if col != 'volume' else 0.0
            if abs(local_value - remote_value) > tolerance:
                mismatches.append({
                    'date': str(row['date']),
                    'column': col,
                    'local': local_value,
                    'remote': remote_value
                })

    return {
        'success': len(mismatches) == 0,
        'symbol': symbol,
        'rows_checked': len(merged),
        'latest_local_date': str(local['date'].max()),
        'latest_remote_date': str(remote['date'].max()),
        'mismatches': mismatches,
        'message': 'verified' if not mismatches else f'{len(mismatches)} mismatches found'
    }
