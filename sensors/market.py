"""
deepbrain/sensors/market.py — Market data sensor (Bitunix WebSocket).

DISARMED: Does not connect to anything by default. Reads from configurable
data source or noop. Real connection only when explicitly configured.
"""

from .base import BaseSensor, SenseEvent


class MarketPriceSensor(BaseSensor):
    """Sense price movements from a candle/tick stream."""

    sense_type = "price_movement"
    default_interval = 5.0  # poll every 5s

    def __init__(self, stream_name: str = "market_price", interval: float | None = None):
        super().__init__(stream_name, interval)
        self._previous_price: float | None = None
        self._connected = False

    def _poll(self) -> SenseEvent | None:
        # DISARMED: No connection by default.
        if not self._connected:
            return None

        # TODO: Real WebSocket read goes here.
        # Placeholder: reads from a temp file if it exists (for testing)
        import os
        feed_path = "/tmp/deepbrain-market-feed"
        if os.path.exists(feed_path):
            raw = open(feed_path).read().strip()
            if raw:
                try:
                    price = float(raw)
                    intensity = 0.0
                    if self._previous_price is not None:
                        pct = abs(price - self._previous_price) / self._previous_price
                        intensity = min(pct * 10, 1.0)  # 10% move = 1.0
                    self._previous_price = price
                    return SenseEvent(
                        sensor_name=self.__class__.__name__,
                        stream_name=self.stream_name,
                        sense_type=self.sense_type,
                        intensity=intensity,
                        raw_data={"price": price, "change_pct": pct if self._previous_price else 0},
                    )
                except ValueError:
                    pass
        return None

    def connect(self, config: dict):
        """Enable the sensor with configuration."""
        self._connected = True
        # TODO: Real Bitunix WS connect in v2
        pass


class OrderbookSensor(BaseSensor):
    """Sense orderbook imbalance."""

    sense_type = "liquidity"
    default_interval = 5.0

    def __init__(self, stream_name: str = "market_orderbook", interval: float | None = None):
        super().__init__(stream_name, interval)
        self._connected = False

    def _poll(self) -> SenseEvent | None:
        if not self._connected:
            return None
        # DISARMED placeholder
        return None

    def connect(self, config: dict):
        self._connected = True