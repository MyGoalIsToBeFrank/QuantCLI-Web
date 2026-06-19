"""
通用注册表基类

为 Pipeline / Strategy / Model 等提供一致的注册/发现/创建接口。
"""

from typing import Any, Dict, Generic, List, Type, TypeVar

T = TypeVar('T')


class SimpleRegistry(Generic[T]):
    """
    简单类型注册表。

    子类在 __init__ 中调用 self.register(...) 注册所有实现类即可。
    """

    def __init__(self):
        self._items: Dict[str, Type[T]] = {}

    def register(self, item_cls: Type[T], *, key: str = None) -> Type[T]:
        """
        注册一个实现类。

        默认 key 为 item_cls.name；可通过 key 参数覆盖。
        """
        name = key or getattr(item_cls, 'name', item_cls.__name__)
        self._items[name] = item_cls
        return item_cls

    def get(self, name: str) -> Type[T]:
        if name not in self._items:
            raise KeyError(f'未注册: {name}')
        return self._items[name]

    def create(self, name: str, *args, **kwargs) -> T:
        return self.get(name)(*args, **kwargs)

    def list_names(self) -> List[str]:
        return list(self._items.keys())

    def list_items(self) -> Dict[str, Type[T]]:
        return dict(self._items)
