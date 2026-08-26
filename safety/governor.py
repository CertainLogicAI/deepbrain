"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/safety/governor.py — Global kill switch, per-stream circuit breakers, rate limiters.

Disarmed by default. All thresholds set to maximum safety. No autonomous action possible
until Anton explicitly lowers a threshold.
"""

import os
import time
from pathlib import Path
from threading import Lock

# ── Path for the kill-switch sentinel file ──────────────────────────
KILL_SWITCH_PATH = Path("/tmp/deepbrain-safe")

# ── In-memory rate-limit buckets ────────────────────────────────────
class RateBucket:
    """Simple sliding-window rate limiter per stream."""
    def __init__(self, max_actions: int, window_seconds: float = 3600.0):
        self.max_actions = max_actions          # 0 = disarmed
        self.window = window_seconds
        self.entries: list[float] = []
        self._lock = Lock()

    def allow(self) -> bool:
        if self.max_actions <= 0:
            return False  # disarmed
        with self._lock:
            now = time.time()
            cutoff = now - self.window
            self.entries = [t for t in self.entries if t > cutoff]
            if len(self.entries) >= self.max_actions:
                return False
            self.entries.append(now)
            return True

    def reset(self, new_max: int = 0):
        with self._lock:
            self.max_actions = new_max
            self.entries.clear()


class Governor:
    """
    Central safety governor.

    Disarmed defaults (read-only properties):
        - global_disarmed()  -> True  (kill switch present)
        - stream_allowed()   -> False (max_actions = 0)
        - dissonance_tier()  -> "stop" (all thresholds = 100+)
        - trust_level()      -> "untrusted"
    """

    def __init__(self):
        # Per-stream rate buckets  stream_name -> RateBucket
        self._buckets: dict[str, RateBucket] = {}

        # Dissonance thresholds  (low, high) -> tier name
        # Disarmed: everything maps to "stop"
        self._tiers = {
            (0, 300): "stop",
        }

        # Stream trust levels  stream_name -> "trusted"|"semi"|"untrusted"
        # Disarmed: all untrusted
        self._stream_trust: dict[str, str] = {}

        self._lock = Lock()

    # ── Kill switch ─────────────────────────────────────────────────

    @staticmethod
    def global_disarmed() -> bool:
        """True when kill-switch file exists (disarmed = safe)."""
        return KILL_SWITCH_PATH.exists()

    @staticmethod
    def arm():
        """Delete kill-switch file → autonomous actions allowed."""
        if KILL_SWITCH_PATH.exists():
            KILL_SWITCH_PATH.unlink()

    @staticmethod
    def disarm():
        """Touch kill-switch file → all autonomous actions blocked."""
        KILL_SWITCH_PATH.touch()

    # ── Stream rate limits ──────────────────────────────────────────

    def register_stream(self, name: str, max_actions_per_hour: int = 0):
        """Register a stream. Default: 0 = disarmed."""
        self._buckets[name] = RateBucket(max_actions_per_hour)

    def stream_allowed(self, name: str) -> bool:
        """Check if stream is within rate limit."""
        if self.global_disarmed():
            return False
        bucket = self._buckets.get(name)
        if bucket is None:
            return False
        return bucket.allow()

    def set_stream_rate(self, name: str, max_per_hour: int):
        if name in self._buckets:
            self._buckets[name].reset(max_per_hour)

    # ── Dissonance tiers ────────────────────────────────────────────

    def set_tiers(self, tier_map: dict[tuple[int, int], str]):
        """
        Set dissonance-to-tier mapping.
        Example:  {(0,30): "auto", (30,50): "explore", (50,70): "conservative",
                    (70,100): "escalate", (100,300): "stop"}
        """
        with self._lock:
            self._tiers = dict(sorted(tier_map.items()))

    def tier_for(self, dissonance: float) -> str:
        """Map a dissonance score to its execution tier."""
        with self._lock:
            for (lo, hi), tier in self._tiers.items():
                if lo <= dissonance < hi:
                    return tier
        return "stop"  # fallback

    # ── Stream trust ────────────────────────────────────────────────

    def set_trust(self, stream_name: str, level: str):
        """level: 'trusted', 'semi', 'untrusted'"""
        assert level in ("trusted", "semi", "untrusted"), f"Invalid trust level: {level}"
        with self._lock:
            self._stream_trust[stream_name] = level

    def trust_level(self, stream_name: str) -> str:
        with self._lock:
            return self._stream_trust.get(stream_name, "untrusted")

    @staticmethod
    def trust_dissonance_floor(level: str) -> float:
        """Minimum dissonance contribution from stream trust."""
        return {"trusted": 0.0, "semi": 20.0, "untrusted": 60.0}.get(level, 60.0)


# ── Singleton ───────────────────────────────────────────────────────
_gov: Governor | None = None


def get_governor() -> Governor:
    global _gov
    if _gov is None:
        _gov = Governor()
    return _gov