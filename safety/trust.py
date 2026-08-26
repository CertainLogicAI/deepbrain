"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/safety/trust.py — Per-stream trust model.

Trust tiers:
    trusted     (localhost files, signed sources)     → dissonance floor 0
    semi        (API with key, authenticated WS)      → dissonance floor 20
    untrusted   (public webhooks, unauthenticated)     → dissonance floor 60, no auto actions
"""

from dataclasses import dataclass

DISARMED_FLOOR = 60.0  # all streams start untrusted


@dataclass(frozen=True)
class TrustProfile:
    """Immutable trust configuration for one stream."""
    level: str               # trusted | semi | untrusted
    dissonance_floor: float
    allows_auto_execute: bool
    allows_explore: bool
    allows_alert: bool
    max_trades_per_hour: int
    max_alerts_per_hour: int

    @classmethod
    def make(cls, level: str) -> "TrustProfile":
        floors = {"trusted": 0.0, "semi": 20.0, "untrusted": 60.0}
        return cls(
            level=level,
            dissonance_floor=floors.get(level, 60.0),
            allows_auto_execute=(level == "trusted"),
            allows_explore=(level in ("trusted", "semi")),
            allows_alert=True,
            max_trades_per_hour={"trusted": 12, "semi": 4, "untrusted": 0}[level],
            max_alerts_per_hour={"trusted": 60, "semi": 30, "untrusted": 10}[level],
        )


# Default registry — all untrusted until configured
REGISTRY: dict[str, TrustProfile] = {}


def register(stream_name: str, level: str):
    REGISTRY[stream_name] = TrustProfile.make(level)


def profile(stream_name: str) -> TrustProfile:
    return REGISTRY.get(stream_name, TrustProfile.make("untrusted"))


def is_armed(stream_name: str) -> bool:
    """True only if this stream is configured for any action capability."""
    p = profile(stream_name)
    return p.max_trades_per_hour > 0 or p.max_alerts_per_hour > 0