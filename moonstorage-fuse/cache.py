import abc
import dataclasses
import datetime
import os
import shutil
from typing import Any


@dataclasses.dataclass
class CachedField:
    value: Any
    until: datetime.datetime


class CachedFieldsStorage:
    def __init__(self):
        self._storage = dict()

    def is_exist(self, key: str) -> bool:
        if key not in self._storage:
            return False

        field = self._storage[key]

        if datetime.datetime.now() > field.until:
            return False

        return True

    @abc.abstractmethod
    def get(self, key: str) -> Any:
        ...

    def set(self, key: str, value: Any, ttl: datetime.timedelta) -> None:
        self._storage[key] = CachedField(value=value,
                                         until=datetime.datetime.now() + ttl)

    def clear(self):
        pass


class CachedFieldsStorageInMemory(CachedFieldsStorage):
    def __init__(self):
        super().__init__()

    def get(self, key: str) -> Any:
        return self._storage[key].value


class CachedFieldsStorageInFiles(CachedFieldsStorage):
    def __init__(self, cache_dir: str):
        super().__init__()

        self.__cache_dir = cache_dir

        os.makedirs(cache_dir, exist_ok=True)

    def get(self, key: str) -> Any:
        with open(self._storage[key].value, 'rb') as f:
            return f.read()

    def get_with_offset(self, key: str, offset: int, size: int):
        with open(self._storage[key].value, 'rb') as f:
            f.seek(offset)

            return f.read(size)

    def clear(self):
        shutil.rmtree(self.__cache_dir)

    @property
    def cache_dir(self) -> str:
        return self.__cache_dir
