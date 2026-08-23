"""L1 RAM-cached Scratchpad."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock

class ScratchpadStore:
    def __init__(self, max_entries: int):
        self.max_entries = max_entries
        self._stores: dict[str, OrderedDict[str, str]] = {}
        self._lock = Lock()

    def _get_store(self, project_id: str) -> OrderedDict[str, str]:
        if project_id not in self._stores:
            self._stores[project_id] = OrderedDict()
        return self._stores[project_id]

    def set(self, project_id: str, key: str, value: str) -> None:
        with self._lock:
            store = self._get_store(project_id)
            if key in store: store.move_to_end(key)
            else: store[key] = value
            
            while len(store) > self.max_entries:
                store.popitem(last=False)

    def get(self, project_id: str, key: str) -> str | None:
        with self._lock:
            store = self._get_store(project_id)
            if key in store:
                store.move_to_end(key)
                return store[key]
            return None

    def delete(self, project_id: str, key: str) -> bool:
        with self._lock:
            store = self._get_store(project_id)
            if key in store:
                del store[key]
                return True
            return False
