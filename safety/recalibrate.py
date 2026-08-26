"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/safety/recalibrate.py — Weekly dissonance drift detection.

Compares current dissonance distribution against a baseline captured during
calibration. If >15% drift on any metric → flag for human review.
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field

BASELINE_DIR = Path("/data/.openclaw/workspace/data/cognitive-baseline")


@dataclass
class CalibrationBaseline:
    """Captured during passive observation week."""
    mean_dissonance: float = 0.0
    median_dissonance: float = 0.0
    p90_dissonance: float = 0.0                  # 90th percentile
    contradiction_rate: float = 0.0               # fraction of cycles with contradictions
    escalate_rate: float = 0.0                    # fraction routed to escalate/stop
    false_positive_rate: float = 0.0              # escalated things that were fine
    false_negative_rate: float = 0.0              # missed things that mattered
    stream_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class CurrentMetrics:
    """Computed from last N cognitive cycles."""
    mean_dissonance: float = 0.0
    median_dissonance: float = 0.0
    p90_dissonance: float = 0.0
    contradiction_rate: float = 0.0
    escalate_rate: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0


def save_baseline(baseline: CalibrationBaseline, label: str = "initial"):
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINE_DIR / f"{label}.json"
    path.write_text(json.dumps({
        **baseline.__dict__,
        "timestamp": time.time(),
    }, indent=2))


def load_baseline(label: str = "initial") -> CalibrationBaseline | None:
    path = BASELINE_DIR / f"{label}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return CalibrationBaseline(**{k: v for k, v in data.items() if k != "timestamp"})


def detect_drift(baseline: CalibrationBaseline, current: CurrentMetrics) -> list[str]:
    """Compare current vs baseline. Returns list of drift alerts (empty = no drift)."""
    alerts: list[str] = []
    threshold = 0.15  # 15%

    checks = [
        ("mean_dissonance", baseline.mean_dissonance, current.mean_dissonance),
        ("median_dissonance", baseline.median_dissonance, current.median_dissonance),
        ("p90_dissonance", baseline.p90_dissonance, current.p90_dissonance),
        ("contradiction_rate", baseline.contradiction_rate, current.contradiction_rate),
        ("escalate_rate", baseline.escalate_rate, current.escalate_rate),
        ("false_positive_rate", baseline.false_positive_rate, current.false_positive_rate),
        ("false_negative_rate", baseline.false_negative_rate, current.false_negative_rate),
    ]

    for metric, base_val, curr_val in checks:
        if base_val == 0 and curr_val == 0:
            continue
        if base_val == 0:
            drift = abs(curr_val)
        else:
            drift = abs((curr_val - base_val) / base_val)
        if drift > threshold:
            alerts.append(
                f"{metric}: baseline={base_val:.3f}, current={curr_val:.3f}, "
                f"drift={drift*100:.1f}% (>{threshold*100:.0f}%)"
            )

    return alerts


def needs_recalibration(baseline: CalibrationBaseline, current: CurrentMetrics) -> bool:
    return len(detect_drift(baseline, current)) > 0