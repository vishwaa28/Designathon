from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class RecoveryState(TypedDict, total=False):
    """Shared LangGraph state. Kept JSON-serialisable; heavy artifacts live in the store."""

    incident_id: str
    event: dict[str, Any]
    detection: dict[str, Any]
    impact: dict[str, Any]
    infra: dict[str, Any]
    options: list[dict[str, Any]]
    recommendation: dict[str, Any]
    plan_version: int
    preferences: dict[str, Any]
    adjustments: dict[str, Any]
    decision: dict[str, Any]
    notifications: dict[str, Any]
    history: Annotated[list[dict[str, Any]], operator.add]
