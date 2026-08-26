"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/sensors/ecosystem.py — External ecosystem sensor (GitHub, ClawHub, webhook).

UNTRUSTED by default. Only triggers alerts, never autonomous actions.
"""

import time
from .base import BaseSensor, SenseEvent


class WebhookSensor(BaseSensor):
    """Sense incoming webhook events.

    DISARMED: No connection by default. Only reads from a temp file if available.
    """

    sense_type = "ecosystem"
    default_interval = 30.0

    def __init__(self, stream_name: str = "webhook", interval: float | None = None):
        super().__init__(stream_name, interval)
        self._enabled = False
        self._last_event_id: str | None = None

    def _poll(self) -> SenseEvent | None:
        if not self._enabled:
            return None

        # Placeholder: reads from temp file for testing
        import os, json
        path = "/tmp/deepbrain-webhook-feed"
        if os.path.exists(path):
            raw = open(path).read().strip()
            if raw:
                try:
                    data = json.loads(raw)
                    event_id = data.get("id", "")
                    if event_id and event_id != self._last_event_id:
                        self._last_event_id = event_id
                        return SenseEvent(
                            sensor_name=self.__class__.__name__,
                            stream_name=self.stream_name,
                            sense_type=self.sense_type,
                            intensity=0.5,  # moderate — can't verify integrity
                            raw_data=data,
                        )
                except (json.JSONDecodeError, ValueError):
                    pass
        return None

    def enable(self):
        self._enabled = True


class SilenceSensor(BaseSensor):
    """Sense absence of data from any other sensor.

    This sensor wraps another sensor and fires when it goes silent.
    """

    sense_type = "absence"
    default_interval = 15.0  # check frequently

    def __init__(self, target_sensor_name: str, stream_name: str | None = None,
                 expected_interval: float = 60.0, interval: float | None = None):
        super().__init__(stream_name or f"silence_{target_sensor_name}", interval)
        self._target = target_sensor_name
        self._expected_interval = expected_interval
        self._last_data_time: float | None = None

    def mark_data(self):
        """Call when target sensor produces data."""
        self._last_data_time = time.time()

    def _poll(self) -> SenseEvent | None:
        if self._last_data_time is None:
            return None
        elapsed = time.time() - self._last_data_time
        if elapsed > self._expected_interval * 3:
            intensity = min(elapsed / self._expected_interval / 5, 1.0)
            return SenseEvent(
                sensor_name=self.__class__.__name__,
                stream_name=self.stream_name,
                sense_type=self.sense_type,
                intensity=round(intensity, 3),
                raw_data={"target": self._target, "seconds_silent": round(elapsed, 1)},
            )
        return None