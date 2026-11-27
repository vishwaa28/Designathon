from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProviderUpdate(BaseModel):
    provider: Literal["gemini", "azure"]


class TriggerRequest(BaseModel):
    scenario_id: str


class Preferences(BaseModel):
    priority: Literal["balanced", "passenger", "cost", "speed"] = "balanced"
    max_delay_min: int | None = Field(default=None, ge=15, le=1440)
    avoid_cancellations: bool = False


class DecisionRequest(BaseModel):
    action: Literal["approve", "reject", "replan"]
    option_id: str | None = None
    controller: str = "Duty controller"
    notes: str = ""
    override_reason: str | None = None
    preferences: Preferences | None = None


class UpdateRequest(BaseModel):
    update_type: Literal["restoration_delayed", "early_restoration", "crew_shortage", "inventory_drop"]
    controller: str = "Duty controller"


class WorkOrderPatch(BaseModel):
    status: Literal["DISPATCHED", "ON_SITE", "IN_PROGRESS", "COMPLETED"]


class RebookRequest(BaseModel):
    last_name: str
    leg_trip_id: str
    new_trip_id: str
    seat: str | None = None


class RefundRequest(BaseModel):
    last_name: str
    leg_trip_id: str


class FrameRequest(BaseModel):
    image: str = Field(min_length=100, max_length=2_200_000, description="Base64 JPEG, optionally a data URL")


class RerouteRequest(BaseModel):
    force: bool = False


class DeliveryTestRequest(BaseModel):
    pnr: str | None = None
    channels: list[Literal["EMAIL", "SMS"]] = ["EMAIL", "SMS"]
