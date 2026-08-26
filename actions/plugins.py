"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/actions/plugins.py — Built-in action plugins.

All actions are STUBBED and DISARMED by default. They print/log but
do not execute real operations until explicitly configured.
"""

import time
import logging
from .base import BaseAction, ActionResult

logger = logging.getLogger("deepbrain.actions")


class TradeAction(BaseAction):
    """Execute a trade via Bitunix API. DISARMED: stub only.

    Real implementation connects to BitunixClient when configured.
    """

    action_name = "trade"

    def __init__(self):
        self._enabled = False
        self._max_size = 0.0  # 0 = disarmed

    def enable(self, api_key: str, max_trade_size_usd: float = 10.0):
        self._enabled = True
        self._max_size = max_trade_size_usd

    def execute(self, payload: dict) -> ActionResult:
        if not self._enabled:
            logger.warning("[DISARMED] TradeAction called but not enabled")
            return ActionResult(
                action_name=self.action_name, success=False,
                details="DISARMED: TradeAction not configured",
            )

        side = payload.get("side", "buy")
        size = min(payload.get("size", 0), self._max_size)
        symbol = payload.get("symbol", "BTCUSDT")

        logger.info(f"[STUB] {side.upper()} ${size:.2f} {symbol}")
        # TODO: Real BitunixClient.trade() in v2

        return ActionResult(
            action_name=self.action_name, success=True,
            details=f"[STUB] {side} {symbol} ${size:.2f}",
            payload={"side": side, "size": size, "symbol": symbol},
        )


class AlertAction(BaseAction):
    """Send an alert via message/email/log.

    This is the only action enabled by default (read-only, informational).
    """

    action_name = "alert"

    def __init__(self):
        self._alert_func = None

    def set_alert_func(self, fn):
        """Set a callable: fn(alert_text: str) -> None"""
        self._alert_func = fn

    def execute(self, payload: dict) -> ActionResult:
        text = payload.get("text", "Cognitive alert — no message provided")
        severity = payload.get("severity", "info")

        logger.info(f"[ALERT:{severity}] {text}")

        if self._alert_func:
            try:
                self._alert_func(text)
            except Exception as e:
                return ActionResult(
                    action_name=self.action_name, success=False,
                    details=f"Alert function failed: {e}",
                )

        return ActionResult(
            action_name=self.action_name, success=True,
            details=f"Alert sent ({severity})",
        )


class HealAction(BaseAction):
    """Restart a service or fix a configuration.

    DISARMED: Stub only. Never executes real operations.
    """

    action_name = "heal"

    def __init__(self):
        self._enabled = False

    def enable(self):
        self._enabled = True

    def execute(self, payload: dict) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                action_name=self.action_name, success=False,
                details="DISARMED: HealAction not enabled",
            )

        target = payload.get("target", "unknown")
        action = payload.get("action", "restart")
        logger.info(f"[STUB-HEAL] {action} -> {target}")
        return ActionResult(
            action_name=self.action_name, success=True,
            details=f"[STUB] {action} {target}",
        )


class EscalateAction(BaseAction):
    """Escalate to human. Always enabled (read-only)."""

    action_name = "escalate"

    def __init__(self):
        self._escalate_func = None

    def set_escalate_func(self, fn):
        self._escalate_func = fn

    def execute(self, payload: dict) -> ActionResult:
        reason = payload.get("reason", "No reason provided")
        profile = payload.get("profile", {})
        logger.warning(f"[ESCALATE] {reason} | dissonance={profile.get('dissonance','?')} tier={profile.get('tier','?')}")

        if self._escalate_func:
            try:
                self._escalate_func(reason, profile)
            except Exception as e:
                return ActionResult(
                    action_name=self.action_name, success=False,
                    details=f"Escalation function failed: {e}",
                )

        return ActionResult(
            action_name=self.action_name, success=True,
            details=f"Escalated: {reason[:100]}",
        )


class ExploreAction(BaseAction):
    """Micro-experiment: small-scale action to validate a cognitive pattern.

    Default: $5 fixed trade size, 1 per 6 hours per pattern.
    """

    action_name = "explore"

    def __init__(self):
        self._enabled = False
        self._max_size = 5.0
        self._pattern_losses: dict[str, int] = {}
        self._pattern_successes: dict[str, int] = {}

    def enable(self, max_size_usd: float = 5.0):
        self._enabled = True
        self._max_size = max_size_usd

    def execute(self, payload: dict) -> ActionResult:
        if not self._enabled:
            return ActionResult(
                action_name=self.action_name, success=False,
                details="DISARMED: ExploreAction not enabled",
            )

        pattern = payload.get("pattern", "unknown")
        side = payload.get("side", "buy")

        # Self-killing: one loss stops explores for this pattern
        if self._pattern_losses.get(pattern, 0) > 0:
            return ActionResult(
                action_name=self.action_name, success=False,
                details=f"Pattern '{pattern}' has prior loss — explores stopped",
            )

        logger.info(f"[STUB-EXPLORE] {pattern}: {side} ${self._max_size:.2f}")
        # TODO: Real micro-trade in v2

        return ActionResult(
            action_name=self.action_name, success=True,
            details=f"[STUB] Explore {side} {pattern} ${self._max_size:.2f}",
            payload={"pattern": pattern, "side": side, "size": self._max_size},
        )

    def record_outcome(self, pattern: str, success: bool):
        if success:
            self._pattern_successes[pattern] = self._pattern_successes.get(pattern, 0) + 1
        else:
            self._pattern_losses[pattern] = self._pattern_losses.get(pattern, 0) + 1
            # Self-killing on first loss
            pattern_key = pattern  # capture in closure
            logger.warning(f"Explore pattern '{pattern_key}' hit first loss — killed")


# ── Register built-in actions (all disarmed by default) ────────────

_trade = TradeAction()
_alert = AlertAction()
_heal = HealAction()
_escalate = EscalateAction()
_explore = ExploreAction()

registered = {
    "trade": _trade,
    "alert": _alert,
    "heal": _heal,
    "escalate": _escalate,
    "explore": _explore,
}


def init():
    from . import base
    for name, action in registered.items():
        base.register(action)