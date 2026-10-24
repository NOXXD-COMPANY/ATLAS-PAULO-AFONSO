"""Cache binário de tiles com limites de tempo, quantidade e memória."""

import time
from collections import OrderedDict
from threading import Lock


class TileCache:
    def __init__(self, max_bytes=32 * 1024 * 1024, max_items=64, ttl=300, clock=None):
        self.max_bytes = max_bytes
        self.max_items = max_items
        self.ttl = ttl
        self.clock = clock or time.monotonic
        self.entries = OrderedDict()
        self.size = 0
        # O pré-aquecimento grava de outra thread que não a do event loop.
        self.lock = Lock()

    def _remove(self, key):
        _, body = self.entries.pop(key)
        self.size -= len(body)

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return None
            expires, body = entry
            if expires <= self.clock():
                self._remove(key)
                return None
            self.entries.move_to_end(key)
            return body

    def put(self, key, body):
        with self.lock:
            if key in self.entries:
                self._remove(key)
            if len(body) > self.max_bytes:
                return
            while self.entries and (self.size + len(body) > self.max_bytes or len(self.entries) >= self.max_items):
                self._remove(next(iter(self.entries)))
            self.entries[key] = (self.clock() + self.ttl, body)
            self.size += len(body)

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.size = 0
