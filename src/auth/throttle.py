"""Bounded in-memory attempt counters, not a cache of authentication results."""

from collections import deque
import hashlib
import hmac
import secrets
from threading import Lock
import time


class AttemptLimiter:
    def __init__(self, *, attempts=5, window_seconds=300, global_attempts=60):
        self.attempts, self.window_seconds, self.global_attempts = attempts, window_seconds, global_attempts
        self._key = secrets.token_bytes(32)
        self._buckets = {}
        self._global = deque()
        self._lock = Lock()

    def _identity(self, username):
        normalized = username.strip().casefold() if isinstance(username,str) else ""
        return hmac.new(self._key,normalized.encode("utf-8",errors="replace"),hashlib.sha256).digest()

    def reserve(self, username, *, now=None):
        now = time.monotonic() if now is None else now
        key = self._identity(username)
        cutoff = now - self.window_seconds
        with self._lock:
            while self._global and self._global[0] <= cutoff:
                self._global.popleft()
            for existing in list(self._buckets):
                events = self._buckets[existing]
                while events and events[0] <= cutoff:
                    events.popleft()
                if not events:
                    del self._buckets[existing]
            events = self._buckets.get(key,deque())
            if len(events) >= self.attempts or len(self._global) >= self.global_attempts:
                return False
            events.append(now)
            self._buckets[key] = events
            self._global.append(now)
            return True

    def successful(self, username):
        with self._lock:
            self._buckets.pop(self._identity(username),None)


DEFAULT_LIMITER = AttemptLimiter()
