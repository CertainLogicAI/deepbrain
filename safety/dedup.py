"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/safety/dedup.py — Action deduplication cache.

Prevents the same cognitive profile + same proposed action from executing
while the first occurrence's outcome is still in flight.
"""

import hashlib
import json
import time
from threading import Lock


class ActionDedupCache:
    """
    Key: SHA-256 of (cognitive_profile_json + action_name)
    Value: {"in_flight": bool, "outcome": str|None, "timestamp": float}
    """

    def __init__(self, ttl_seconds: float = 300.0):
        self._ttl = ttl_seconds
        self._cache: dict[str, dict] = {}
        self._lock = Lock()

    # ── ──

    @staticmethod
    def _key(profile: dict, action_name: str) -> str:
        raw = json.dumps(profile, sort_keys=True) + "::" + action_name
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── ──

    def is_in_flight(self, profile: dict, action_name: str) -> bool:
        """True if this profile+action is already being executed."""
        k = self._key(profile, action_name)
        with self._lock:
            entry = self._cache.get(k)
            if entry is None:
                return False
            if time.time() - entry["timestamp"] > self._ttl:
                del self._cache[k]
                return False
            return entry.get("in_flight", False)

    def mark_in_flight(self, profile: dict, action_name: str):
        k = self._key(profile, action_name)
        with self._lock:
            self._cache[k] = {"in_flight": True, "outcome": None, "timestamp": time.time()}

    def resolve(self, profile: dict, action_name: str, outcome: str):
        """Mark as resolved with an outcome string (success/fail/error)."""
        k = self._key(profile, action_name)
        with self._lock:
            entry = self._cache.get(k)
            if entry:
                entry["in_flight"] = False
                entry["outcome"] = outcome
                entry["timestamp"] = time.time()

    def clear_expired(self):
        now = time.time()
        with self._lock:
            stale = [k for k, v in self._cache.items() if now - v["timestamp"] > self._ttl]
            for k in stale:
                del self._cache[k]
            return len(stale)


# Singleton
_dedup: ActionDedupCache | None = None


def get_dedup() -> ActionDedupCache:
    global _dedup
    if _dedup is None:
        _dedup = ActionDedupCache()
    return _dedup