import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from copy import deepcopy


class CacheProvider(ABC):
    @abstractmethod
    def get(self, key: tuple): ...

    @abstractmethod
    def set(self, key: tuple, value, ttl: int = 60): ...


class InMemoryCache(CacheProvider):
    """Optional bounded process-local cache; never authoritative state."""

    def __init__(self, capacity=128):
        self.capacity = capacity
        self.values = OrderedDict()

    def get(self, key):
        entry = self.values.get(key)
        if not entry:
            return None
        if entry[0] <= time.monotonic():
            del self.values[key]
            return None
        self.values.move_to_end(key)
        return deepcopy(entry[1])

    def set(self, key, value, ttl=60):
        self.values[key] = (time.monotonic() + ttl, deepcopy(value))
        self.values.move_to_end(key)
        while len(self.values) > self.capacity:
            self.values.popitem(last=False)


def scoped_key(scope, revision, query):
    return (scope.tenant_id, scope.user_id, scope.role, revision, query)
