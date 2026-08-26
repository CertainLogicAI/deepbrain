"""
deepbrain/sensors/logs.py — Log stream sensor.

Tails log files for error rate spikes. Works on localhost files (trusted).
"""

import os
import time
from collections import deque
from pathlib import Path

from .base import BaseSensor, SenseEvent


class ErrorRateSensor(BaseSensor):
    """Sense error rate spikes from log files."""

    sense_type = "failure"
    default_interval = 30.0

    def __init__(self, stream_name: str = "system_logs", interval: float | None = None):
        super().__init__(stream_name, interval)
        self._log_paths: list[Path] = []
        self._error_counts: deque = deque(maxlen=60)          # 60 samples max
        self._baseline_rate: float = 0.0
        self._calibrated: bool = False

    def add_log_path(self, path: str):
        p = Path(path)
        if p.exists():
            self._log_paths.append(p)

    def _poll(self) -> SenseEvent | None:
        count = 0
        for path in self._log_paths:
            try:
                if path.stat().st_mtime > (time.time() - self.interval):
                    text = path.read_text(errors="replace")
                    # Simple error matching; expandable
                    count += text.count("ERROR") + text.count("Traceback") + text.count("panic")
            except OSError:
                pass

        # First 10 samples = calibration
        self._error_counts.append(count)
        if len(self._error_counts) < 10:
            self._baseline_rate = sum(self._error_counts) / len(self._error_counts)
            return None

        # Recompute baseline every 10 samples
        if len(self._error_counts) % 10 == 0:
            self._baseline_rate = sum(self._error_counts) / len(self._error_counts)

        if self._baseline_rate > 0:
            intensity = min(count / (self._baseline_rate * 3), 1.0)
        else:
            intensity = 0.0 if count == 0 else min(count / 5.0, 1.0)

        if intensity > 0.5:
            return SenseEvent(
                sensor_name=self.__class__.__name__,
                stream_name=self.stream_name,
                sense_type=self.sense_type,
                intensity=round(intensity, 3),
                raw_data={"error_count": count, "baseline": round(self._baseline_rate, 2)},
            )
        return None


class HeartbeatSensor(BaseSensor):
    """Sense missing heartbeat from a known service."""

    sense_type = "heartbeat"
    default_interval = 60.0

    def __init__(self, stream_name: str = "deepbrain_heartbeat", interval: float | None = None):
        super().__init__(stream_name, interval)
        self._last_heartbeat: float | None = None

    def ping(self):
        """Call this when a heartbeat is received."""
        self._last_heartbeat = time.time()

    def _poll(self) -> SenseEvent | None:
        if self._last_heartbeat is None:
            return None
        elapsed = time.time() - self._last_heartbeat
        expected = self.interval * 3  # 3 missed intervals = alert
        if elapsed > expected:
            intensity = min(elapsed / expected / 2, 1.0)
            return SenseEvent(
                sensor_name=self.__class__.__name__,
                stream_name=self.stream_name,
                sense_type=self.sense_type,
                intensity=round(intensity, 3),
                raw_data={"seconds_since_heartbeat": round(elapsed, 1)},
            )
        return None