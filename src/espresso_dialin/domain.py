"""Validated live acquisition records; measurements never imply recommendations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from espresso_dialin.dose_control import DoseRecommendation


def utc_now() -> datetime:
    return datetime.now(UTC)


def positive(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")


def required(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


def aware(value: datetime) -> None:
    if value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")


class CorrectionMode(StrEnum):
    NONE = "NONE"
    TO_TARGET = "TO_TARGET"
    MEASURED = "MEASURED"


class ShotStatus(StrEnum):
    PENDING_GRINDING = "PENDING_GRINDING"
    PENDING_BREWING = "PENDING_BREWING"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, kw_only=True)
class ShotResolution:
    status: ShotStatus
    recorded_at: datetime
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, ShotStatus) or self.status not in (
            ShotStatus.ABANDONED,
            ShotStatus.INVALIDATED,
        ):
            raise ValueError("resolution must abandon or invalidate a shot")
        aware(self.recorded_at)
        required(self.reason, "resolution reason")


@dataclass(frozen=True, kw_only=True)
class Session:
    id: str
    bean_id: str
    bean_name: str
    started_at: datetime
    grinder: str = "Baratza Sette 270"
    machine: str = "Sage/Breville Dual Boiler (BES920/SES920)"
    roaster: str | None = None
    roast_date: date | None = None
    bag_opened_date: date | None = None
    ended_at: datetime | None = None
    target_puck_dose_g: float = 18.0
    target_yield_g: float = 36.0
    target_time_min_s: float = 30.0
    target_time_max_s: float = 35.0

    def __post_init__(self) -> None:
        for name in ("id", "bean_id", "bean_name", "grinder", "machine"):
            required(getattr(self, name), name)
        for name in (
            "target_puck_dose_g",
            "target_yield_g",
            "target_time_min_s",
            "target_time_max_s",
        ):
            positive(getattr(self, name), name)
        if self.target_time_max_s < self.target_time_min_s:
            raise ValueError("brew-time upper bound must be at least the lower bound")
        aware(self.started_at)
        if self.ended_at is not None:
            aware(self.ended_at)
            if self.ended_at < self.started_at:
                raise ValueError("session cannot end before it starts")


@dataclass(frozen=True, kw_only=True)
class Plan:
    """Frozen pre-shot choice, including explicit manual plans and model shadows."""

    id: str
    session_id: str
    target_sequence: int
    created_at: datetime
    setting: str
    duration_s: float
    target_output_g: float
    selected: bool
    model: DoseRecommendation | None = None

    @property
    def strategy_id(self) -> str:
        return self.model.strategy_id if self.model else "manual"

    def __post_init__(self) -> None:
        for name in ("id", "session_id", "setting"):
            required(getattr(self, name), name)
        if self.target_sequence <= 0:
            raise ValueError("target sequence must be positive")
        aware(self.created_at)
        positive(self.duration_s, "planned duration")
        positive(self.target_output_g, "target output")
        if self.model is not None and (
            self.model.recommendation_id != self.id
            or self.model.session_id != self.session_id
            or self.model.grinder_setting != self.setting
            or self.model.recommended_duration_s != self.duration_s
            or self.model.target_output_g != self.target_output_g
            or self.model.created_at != self.created_at
            or self.model.history_through_sequence >= self.target_sequence
        ):
            raise ValueError("model context must match the frozen plan")


@dataclass(frozen=True, kw_only=True)
class GrindingResult:
    setting: str
    duration_s: float
    output_g: float
    correction: CorrectionMode
    puck_dose_g: float | None = None

    def __post_init__(self) -> None:
        required(self.setting, "actual setting")
        positive(self.duration_s, "actual grind duration")
        positive(self.output_g, "grinder output")
        if not isinstance(self.correction, CorrectionMode):
            raise ValueError("unknown dose correction mode")
        if self.correction == CorrectionMode.MEASURED:
            if self.puck_dose_g is None:
                raise ValueError("MEASURED requires a measured puck dose")
            positive(self.puck_dose_g, "puck dose")
        elif self.puck_dose_g is not None:
            raise ValueError("record a separate puck mass only with MEASURED")


@dataclass(frozen=True, kw_only=True)
class BrewingResult:
    duration_s: float
    yield_g: float
    purged_before_shot: bool = False
    obviously_bad_shot: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        positive(self.duration_s, "brew duration")
        positive(self.yield_g, "final yield")


@dataclass(frozen=True, kw_only=True)
class Shot:
    id: str
    session_id: str
    sequence: int
    created_at: datetime
    selected_recommendation_id: str
    grinding: GrindingResult | None = None
    brewing: BrewingResult | None = None
    completed_at: datetime | None = None
    grinding_recorded_at: datetime | None = None
    resolution: ShotResolution | None = None

    @property
    def plan_frozen_at(self) -> datetime:
        return self.created_at

    @property
    def brewing_recorded_at(self) -> datetime | None:
        return self.completed_at

    @property
    def status(self) -> ShotStatus:
        if self.resolution is not None:
            return self.resolution.status
        if self.completed_at is not None:
            return ShotStatus.COMPLETED
        return ShotStatus.PENDING_BREWING if self.grinding else ShotStatus.PENDING_GRINDING

    @property
    def pending(self) -> bool:
        return self.status in (ShotStatus.PENDING_GRINDING, ShotStatus.PENDING_BREWING)

    @property
    def terminal_at(self) -> datetime | None:
        return self.resolution.recorded_at if self.resolution else self.completed_at

    @property
    def dose_eligible(self) -> bool:
        return self.grinding is not None and self.status in (
            ShotStatus.COMPLETED,
            ShotStatus.ABANDONED,
        )

    def validate_resolution(self, resolution: ShotResolution) -> None:
        if self.resolution is not None:
            raise ValueError("shot already has an abandonment/invalidation record")
        if resolution.status == ShotStatus.ABANDONED and not self.pending:
            raise ValueError("only a pending shot can be abandoned")
        latest = self.completed_at or self.grinding_recorded_at or self.created_at
        if resolution.recorded_at < latest:
            raise ValueError("resolution cannot precede the recorded evidence")

    def __post_init__(self) -> None:
        for name in ("id", "session_id", "selected_recommendation_id"):
            required(getattr(self, name), name)
        if self.sequence <= 0:
            raise ValueError("shot sequence must be positive")
        aware(self.created_at)
        if self.grinding_recorded_at is not None:
            aware(self.grinding_recorded_at)
            if self.grinding is None or self.grinding_recorded_at < self.created_at:
                raise ValueError("grinding timestamp requires grinding after plan freezing")
        if self.brewing is not None and self.grinding is None:
            raise ValueError("grinding must precede brewing")
        if (self.brewing is None) != (self.completed_at is None):
            raise ValueError("completion requires a brewing result")
        if self.completed_at is not None:
            aware(self.completed_at)
            if self.completed_at < self.created_at:
                raise ValueError("completion cannot precede creation")
            if self.grinding_recorded_at and self.completed_at < self.grinding_recorded_at:
                raise ValueError("brewing record cannot precede grinding record")
        if self.resolution is not None:
            latest = self.completed_at or self.grinding_recorded_at or self.created_at
            if self.resolution.recorded_at < latest:
                raise ValueError("resolution cannot precede the recorded evidence")
            if self.resolution.status == ShotStatus.ABANDONED and self.brewing is not None:
                raise ValueError("completed brew cannot be abandoned")


def compatible_dose_block(shots: list[Shot], setting: str) -> list[Shot]:
    """Unknown/invalid data break continuity instead of silently bridging a transition."""
    compatible: list[Shot] = []
    for shot in reversed(shots):
        if not shot.dose_eligible or shot.grinding is None or shot.grinding.setting != setting:
            break
        compatible.append(shot)
    return list(reversed(compatible))
