"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/sensors/base.py — Abstract base sensor and sensor registry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SenseEvent:
    """Fired by a sensor when data arrives or silence is detected."""
    sensor_name: str
    stream_name: str
    sense_type: str                # e.g. "price_movement", "error_rate", "absence"
    intensity: float               # 0.0 (nothing) → 1.0 (max)
    raw_data: Any = None
    metadata: dict = field(default_factory=dict)


class BaseSensor(ABC):
    """
    Abstract sensor.

    Subclasses implement:
        - _poll() -> SenseEvent | None   (one cycle of data collection)

    Subclasses set class-level:
        - sense_type: str            (used for contradiction matching)
        - default_interval: float    (seconds between polls, for silence monitor)
    """

    sense_type: str = "generic"
    default_interval: float = 60.0

    def __init__(self, stream_name: str, interval: float | None = None):
        self.stream_name = stream_name
        self.interval = interval or self.default_interval
        self._last_data_time: float | None = None

    @abstractmethod
    def _poll(self) -> SenseEvent | None:
        """Collect one data point. Return None if no new data."""
        ...

    def poll(self) -> SenseEvent | None:
        """Public poll wrapper with silence tracking."""
        event = self._poll()
        if event is not None:
            self._last_data_time = __import__("time").time()
        return event

    @property
    def seconds_since_last_data(self) -> float | None:
        if self._last_data_time is None:
            return None
        return __import__("time").time() - self._last_data_time


# ── Registry ────────────────────────────────────────────────────────

_sensors: dict[str, BaseSensor] = {}


def register(sensor: BaseSensor):
    _sensors[sensor.stream_name] = sensor


def get_all() -> list[BaseSensor]:
    return list(_sensors.values())


def get(stream_name: str) -> BaseSensor | None:
    return _sensors.get(stream_name)