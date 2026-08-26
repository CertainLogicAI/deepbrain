"""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
deepbrain/actions/base.py — Abstract action executor with plugin loader.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionResult:
    """Result of executing one action."""
    action_name: str
    success: bool
    details: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class BaseAction(ABC):
    """Abstract action. Subclass and register to add capabilities."""

    action_name: str = "generic"

    @abstractmethod
    def execute(self, payload: dict) -> ActionResult:
        ...


# ── Registry (empty by default — disarmed) ─────────────────────────

_actions: dict[str, BaseAction] = {}


def register(action: BaseAction):
    _actions[action.action_name] = action


def get(name: str) -> BaseAction | None:
    return _actions.get(name)


def get_all() -> list[BaseAction]:
    return list(_actions.values())


def execute(name: str, payload: dict) -> ActionResult | None:
    action = get(name)
    if action is None:
        return None
    return action.execute(payload)


def clear():
    """Unregister all actions (disarm)."""
    _actions.clear()