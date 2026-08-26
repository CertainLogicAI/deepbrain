"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/cognition/contradiction.py — Contradiction detector.

When two senses fire that should correlate or exclude each other, their
divergence elevates dissonance above the sum of their individual intensities.
"""

from dataclasses import dataclass, field
from math import exp


# Registered contradiction pairs: (sense_a, sense_b, expected_correlation)
# correlation ranges:  -1 (always opposite)  …  +1 (always together)
CONTRADICTION_PAIRS: list[tuple[str, str, float]] = [
    # Price vs liquidity: when price moves, we expect liquidity to be present.
    # Low liquidity during high movement = contradiction
    ("price_movement", "liquidity", +0.6),

    # Error rate vs heartbeat: errors are expected with live heartbeats.
    # High errors with dead heartbeat = system is down, not failing
    ("failure", "heartbeat", -0.4),
]


@dataclass
class ContradictionResult:
    contradictions_found: int = 0
    total_penalty: float = 0.0
    details: list[dict] = field(default_factory=list)


def detect(senses: dict[str, float]) -> ContradictionResult:
    """
    Given a dict of sense_name→intensity, detect contradictions.

    Penalty formula:
        for each pair where both senses fire:
            expected = expected_correlation
            actual = correlation of intensities (simplified: sign_match)
            divergence = abs(expected - actual)  # 0.0 → 2.0 range
            pair_penalty = divergence * min(intensity_a, intensity_b) * 20

    Normalizes to 0-100 scale.
    """
    result = ContradictionResult()

    for sense_a, sense_b, expected_corr in CONTRADICTION_PAIRS:
        a_val = senses.get(sense_a)
        b_val = senses.get(sense_b)

        if a_val is None or b_val is None or a_val == 0.0 or b_val == 0.0:
            continue

        # Simplified: both firing is a positive actual correlation of +1
        actual_corr = 1.0

        # Divergence: 0 = perfectly matches expected, 2 = maximally contradicts
        divergence = abs(expected_corr - actual_corr)

        # Penalty: scaled by signal divergence (further apart = more contradictory)
        signal_divergence = abs(a_val - b_val)
        pair_penalty = divergence * signal_divergence * 20.0

        result.contradictions_found += 1
        result.total_penalty += pair_penalty
        result.details.append({
            "sense_a": sense_a,
            "sense_b": sense_b,
            "expected_corr": expected_corr,
            "actual_corr": actual_corr,
            "divergence": round(divergence, 3),
            "pair_penalty": round(pair_penalty, 3),
        })

    # Soft-cap total penalty at 100
    result.total_penalty = min(result.total_penalty, 100.0)

    return result