"""
基本面分析记录管理

存储每只股票的：
  - 上次分析日期
  - 最新报告路径
  - 建议下次分析日期
  - 历史记录

与 src.data.stock_registry 挂钩，仅接受已注册股票。
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.data.stock_registry import REGISTRY


DEFAULT_RECORDS_PATH = Path('data/fundamental_records.json')
DEFAULT_ARCHIVE_DIR = Path('reports/fundamental')
DEFAULT_INTERVAL_DAYS = 30  # 建议每 30 天进行一次基本面分析


class FundamentalRecords:
    """基本面分析记录管理器"""

    def __init__(self, path: Path = None,
                 archive_dir: Path = None,
                 interval_days: int = DEFAULT_INTERVAL_DAYS):
        self.path = path or DEFAULT_RECORDS_PATH
        self.archive_dir = archive_dir or DEFAULT_ARCHIVE_DIR
        self.interval_days = interval_days
        self._records: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        """从 JSON 文件加载记录"""
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._records = data.get('records', {})
            except Exception as e:
                print(f'[FundamentalRecords] 加载记录失败: {e}')
                self._records = {}
        else:
            self._records = {}

    def save(self) -> None:
        """保存记录到 JSON 文件"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump({
                'meta': {
                    'updated_at': datetime.now().isoformat(),
                    'interval_days': self.interval_days
                },
                'records': self._records
            }, f, ensure_ascii=False, indent=2)

    def _ensure_symbol(self, symbol: str) -> Dict[str, Any]:
        """确保某股票在记录中存在，并同步注册表信息"""
        info = REGISTRY.get(symbol)
        if symbol not in self._records:
            self._records[symbol] = {
                'symbol': info.symbol,
                'name': info.name,
                'market': info.market,
                'last_analysis_date': None,
                'next_due_date': None,
                'report_path': None,
                'history': []
            }
        else:
            # 同步注册表信息（名称可能更新）
            self._records[symbol]['symbol'] = info.symbol
            self._records[symbol]['name'] = info.name
            self._records[symbol]['market'] = info.market
        return self._records[symbol]

    def is_registered(self, symbol: str) -> bool:
        """检查股票是否在注册表中"""
        try:
            REGISTRY.get(symbol)
            return True
        except KeyError:
            return False

    def check(self, symbol: str) -> Dict[str, Any]:
        """
        检查某股票是否需要基本面分析

        返回：
          - symbol, name
          - last_analysis_date
          - next_due_date
          - days_until_due: 距离到期天数（负数表示已到期）
          - is_needed: 是否需要进行新的分析
        """
        if not self.is_registered(symbol):
            raise ValueError(f'{symbol} 不在股票注册表中')

        record = self._ensure_symbol(symbol)
        today = datetime.now().date()
        last_date = record['last_analysis_date']

        if last_date is None:
            next_due = today
            days_until_due = -1
            is_needed = True
        else:
            last = datetime.fromisoformat(last_date).date()
            next_due = last + timedelta(days=self.interval_days)
            days_until_due = (next_due - today).days
            is_needed = days_until_due <= 0

        record['next_due_date'] = next_due.isoformat()
        self.save()

        return {
            'symbol': record['symbol'],
            'name': record['name'],
            'market': record['market'],
            'last_analysis_date': last_date,
            'next_due_date': next_due.isoformat(),
            'days_until_due': days_until_due,
            'is_needed': is_needed
        }

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有已注册股票的基本面分析状态"""
        result = []
        for info in REGISTRY.list_all():
            result.append(self.check(info.symbol))
        return result

    def archive_report(self, symbol: str, source_file: Path) -> Path:
        """
        将外部报告归档到项目目录

        返回归档后的相对路径
        """
        if not self.is_registered(symbol):
            raise ValueError(f'{symbol} 不在股票注册表中')

        source_file = Path(source_file)
        if not source_file.exists():
            raise FileNotFoundError(f'报告文件不存在: {source_file}')

        date_str = datetime.now().strftime('%Y%m%d')
        target_dir = self.archive_dir / symbol
        target_dir.mkdir(parents=True, exist_ok=True)

        ext = source_file.suffix or '.md'
        target_name = f'{date_str}_report{ext}'
        target_path = target_dir / target_name

        # 如果同名文件存在，追加序号
        counter = 1
        while target_path.exists():
            target_name = f'{date_str}_report_{counter}{ext}'
            target_path = target_dir / target_name
            counter += 1

        shutil.copy2(source_file, target_path)
        return target_path

    def write_report(self, symbol: str, source_file: Path) -> Dict[str, Any]:
        """
        写回 Agent 生成的基本面分析报告

        返回更新后的记录摘要
        """
        record = self._ensure_symbol(symbol)
        archived_path = self.archive_report(symbol, source_file)

        today = datetime.now().date().isoformat()

        # 历史记录
        history_entry = {
            'date': today,
            'report_path': str(archived_path),
            'source_file': str(Path(source_file).resolve())
        }
        record['history'].append(history_entry)

        # 更新当前记录
        record['last_analysis_date'] = today
        record['report_path'] = str(archived_path)
        record['next_due_date'] = (
            datetime.now().date() + timedelta(days=self.interval_days)
        ).isoformat()

        self.save()

        return {
            'symbol': record['symbol'],
            'name': record['name'],
            'last_analysis_date': today,
            'report_path': str(archived_path)
        }

    def get_record(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取某股票的完整记录"""
        if not self.is_registered(symbol):
            raise ValueError(f'{symbol} 不在股票注册表中')
        return self._ensure_symbol(symbol)

    def read_report(self, symbol: str) -> Optional[str]:
        """读取某股票最新报告内容"""
        record = self.get_record(symbol)
        report_path = record.get('report_path')
        if not report_path or not Path(report_path).exists():
            return None
        with open(report_path, 'r', encoding='utf-8') as f:
            return f.read()
