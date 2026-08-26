"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/cognition/freshness.py — Dissonance freshness decay.

Old unrejected memories contribute less to cognitive match confidence.
Prevents the system from being confidently wrong about stale patterns.
"""

import math
import time

FRESHNESS_WINDOW_DAYS = 30  # configurable


def freshness_weight(days_since_validation: float) -> float:
    """
    Exponential decay over FRESHNESS_WINDOW_DAYS.

    Example:
        0 days   → weight = 1.0
        30 days  → weight = 0.5
        90 days  → weight = 0.125
        365 days → weight = 0.00195

    Formula: weight = 2^(-days / FRESHNESS_WINDOW_DAYS)
    """
    return 2.0 ** (-days_since_validation / FRESHNESS_WINDOW_DAYS)


def apply_freshness(base_confidence: float, last_validated_timestamp: float | None,
                    now: float | None = None) -> float:
    """
    Apply freshness decay to a base confidence score.

    If last_validated_timestamp is None (never validated), weight = 0.1.
    """
    if now is None:
        now = time.time()
    if last_validated_timestamp is None:
        return base_confidence * 0.1

    days_since = (now - last_validated_timestamp) / 86400.0
    if days_since < 0:
        days_since = 0.0

    return base_confidence * freshness_weight(days_since)


def set_window(days: int):
    """Update the freshness window (for recalibration)."""
    global FRESHNESS_WINDOW_DAYS
    FRESHNESS_WINDOW_DAYS = days