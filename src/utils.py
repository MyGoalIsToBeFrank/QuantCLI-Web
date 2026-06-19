"""
通用工具函数
"""

import json
from datetime import datetime
from pathlib import Path


def ensure_dir(path):
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)


def parse_date(date_val):
    """将多种日期格式转为 date 对象"""
    if hasattr(date_val, 'date'):
        return date_val.date()
    if isinstance(date_val, str):
        # 尝试多种格式
        for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                    '%Y/%m/%d', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%fZ'):
            try:
                return datetime.strptime(date_val[:len(fmt)].replace('Z', ''), fmt).date()
            except Exception:
                continue
        # 处理带时区的情况，如 2024-06-17T04:00:00.000Z
        try:
            dt = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
            return dt.date()
        except Exception:
            pass
    return None


def format_date(d):
    """将 date/datetime 转为字符串"""
    if hasattr(d, 'strftime'):
        return d.strftime('%Y-%m-%d')
    return str(d)


def save_json(path, data):
    """保存 JSON 文件"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path, default=None):
    """加载 JSON 文件"""
    target = Path(path)
    if not target.exists():
        return default
    try:
        with open(target, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'[Utils] 加载 JSON 失败 {target}: {e}')
        return default
