import abc
import dataclasses
import datetime
from typing import Any


@dataclasses.dataclass
class CachedField:
    value: Any
    until: datetime.datetime


class CachedFieldsStorage(abc.ABC):
    @abc.abstractmethod
    def is_exist(self, key: str) -> bool:
        ...

    @abc.abstractmethod
    def get(self, key: str) -> Any:
        ...


class CachedFieldsStorageInMemory(CachedFieldsStorage):
    def __init__(self):
        self.__storage: dict[str, CachedField] = dict()

    def is_exist(self, key: str) -> bool:
        if key not in self.__storage:
            return False

        field = self.__storage[key]

        current_time = datetime.datetime.now()

        if current_time > field.until:
            return False

        return True

    def get(self, key: str) -> Any:
        return self.__storage[key].value

    def set(self, key: str, value: Any, ttl: datetime.timedelta) -> None:
        self.__storage[key] = CachedField(value=value,
                                          until=datetime.datetime.now() + ttl)
