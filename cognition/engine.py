"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/cognition/engine.py — Cognitive engine core.

Perceptual cycle:
    1. Collect fired senses + intensities
    2. Detect contradictions between conflicting senses
    3. Apply stream trust dissonance floor
    4. Apply freshness decay to historical matches
    5. Score total dissonance
    6. Route to execution tier

DISARMED defaults: all senses start at dissonance 100+ (Full Stop).
"""

from dataclasses import dataclass, field
from typing import Any

from deepbrain.safety.governor import Governor, get_governor
from deepbrain.safety.trust import profile as trust_profile
from deepbrain.cognition.contradiction import detect as detect_contradictions, ContradictionResult
from deepbrain.cognition.freshness import apply_freshness


@dataclass
class CognitiveProfile:
    """The complete cognitive state for one perceptual cycle."""
    senses: dict[str, float] = field(default_factory=dict)        # sense_name → intensity
    modalities: list[str] = field(default_factory=list)
    stream_trust: dict[str, str] = field(default_factory=dict)    # stream → trust level
    contradiction_result: ContradictionResult | None = None
    historical_match_confidence: float = 0.0                      # 0.0 (no match) → 1.0 (perfect match)
    freshness_decay: float = 1.0                                   # 1.0 = brand new, 0.0 = fully decayed
    dissonance: float = 0.0                                        # 0 (nothing) → 300 (max)
    tier: str = "stop"
    action_payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "senses": self.senses,
            "modalities": self.modalities,
            "stream_trust": self.stream_trust,
            "contradictions": {
                "count": self.contradiction_result.contradictions_found if self.contradiction_result else 0,
                "penalty": round(self.contradiction_result.total_penalty, 2) if self.contradiction_result else 0.0,
            },
            "historical_match_confidence": round(self.historical_match_confidence, 3),
            "freshness_decay": round(self.freshness_decay, 3),
            "dissonance": round(self.dissonance, 1),
            "tier": self.tier,
            "action_payload": self.action_payload,
            "timestamp": self.timestamp or __import__("time").time(),
        }


class CognitiveEngine:
    """
    Perceptual cycle runner.

    Usage:
        engine = CognitiveEngine()
        profile = engine.cycle(senses={"price_movement": 0.7}, stream_meta={"market_price": "semi"})
    """

    def __init__(self, governor: Governor | None = None):
        self._gov = governor or get_governor()

    def cycle(self, senses: dict[str, float],
              stream_meta: dict[str, str] | None = None,
              historical_confidence: float = 0.0,
              last_validated: float | None = None,
              now: float | None = None) -> CognitiveProfile:
        """
        Run one full perceptual cycle.

        Args:
            senses:          {sense_name: intensity} from all sensory faculties
            stream_meta:     {sense_name: stream_name} for trust lookups
            historical_confidence: 0-1 match against timechain replay
            last_validated:  timestamp of last timechain validation
            now:             current time (for freshness)
        """
        import time
        now = now or time.time()
        stream_meta = stream_meta or {}
        profile = CognitiveProfile(senses=senses, timestamp=now)

        # 1. Detect contradictions
        contradictions = detect_contradictions(senses)
        profile.contradiction_result = contradictions

        # 2. Calculate dissonance components

        # a) Base sensory intensity (sum of all sense intensities, soft-capped at 100)
        base_dissonance = sum(senses.values())
        base_dissonance = min(base_dissonance, 100.0)

        # b) Contradiction penalty (0-100)
        contradiction_penalty = contradictions.total_penalty

        # c) Stream trust floor (0-60)
        if stream_meta:
            trust_floors = [trust_profile(s).dissonance_floor for s in stream_meta.values()]
            trust_floor = max(trust_floors) if trust_floors else 0.0
        else:
            trust_floor = 60.0  # untrusted when unknown

        # d) Freshness decay on historical match
        if historical_confidence > 0:
            fresh_confidence = apply_freshness(historical_confidence, last_validated, now)
            freshness_penalty = (historical_confidence - fresh_confidence) * 50
            profile.historical_match_confidence = historical_confidence
            profile.freshness_decay = fresh_confidence / max(historical_confidence, 0.001)
        else:
            freshness_penalty = 0.0
            profile.freshness_decay = 1.0

        # e) Total dissonance
        dissonance = base_dissonance + contradiction_penalty + trust_floor + freshness_penalty
        dissonance = max(0.0, min(dissonance, 300.0))
        profile.dissonance = dissonance

        # 3. Route to tier
        profile.tier = self._gov.tier_for(dissonance)

        # 4. Determine modalities from firing senses
        profile.modalities = self._classify_modalities(senses)

        return profile

    @staticmethod
    def _classify_modalities(senses: dict[str, float]) -> list[str]:
        """Map active senses to modalities."""
        modalities = []
        if senses.get("price_movement", 0) > 0.2 or senses.get("liquidity", 0) > 0.2:
            modalities.append("trade")
        if senses.get("failure", 0) > 0.3:
            modalities.append("heal")
        if senses.get("absence", 0) > 0.5:
            modalities.append("investigate")
        if senses.get("ecosystem", 0) > 0:
            modalities.append("learn")
        if senses.get("heartbeat", 0) > 0.5 and senses.get("absence", 0) > 0:
            modalities.append("escalate")
        if not modalities:
            modalities.append("observe")
        return modalities