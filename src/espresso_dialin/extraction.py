"""Directional baseline only: linear yield normalization is not physical truth."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from espresso_dialin.domain import Session, Shot, ShotStatus, aware, positive


class ExtractionDirection(StrEnum):
    KEEP = "KEEP"
    FINER = "FINER"
    COARSER = "COARSER"
    NO_UPDATE_BAD_SHOT = "NO_UPDATE_BAD_SHOT"


@dataclass(frozen=True, kw_only=True)
class ExtractionRecommendation:
    id: str
    session_id: str
    target_sequence: int
    source_shot_id: str
    history_through_sequence: int
    created_at: datetime
    target_yield_g: float
    target_time_min_s: float
    target_time_max_s: float
    linear_target_yield_time_s: float
    direction: ExtractionDirection
    strategy_id: str = "linear_yield_direction_baseline"
    model_version: str = "1"

    def __post_init__(self) -> None:
        aware(self.created_at)
        for name in (
            "target_yield_g",
            "target_time_min_s",
            "target_time_max_s",
            "linear_target_yield_time_s",
        ):
            positive(getattr(self, name), name)
        if not 0 < self.history_through_sequence < self.target_sequence:
            raise ValueError("extraction source must precede target shot")
        if self.target_time_max_s < self.target_time_min_s:
            raise ValueError("unordered extraction time band")


def recommend_extraction(
    session: Session, shots: list[Shot], target_sequence: int, created_at: datetime
) -> ExtractionRecommendation | None:
    """Use the latest completed same-session brew, including bad-shot suppression."""
    aware(created_at)
    eligible = [
        s
        for s in shots
        if s.session_id == session.id
        and s.sequence < target_sequence
        and s.status == ShotStatus.COMPLETED
        and s.brewing is not None
        and s.completed_at is not None
        and s.completed_at <= created_at
    ]
    if not eligible:
        return None
    source = max(eligible, key=lambda s: s.sequence)
    assert source.brewing is not None
    brew = source.brewing
    estimate = brew.duration_s * (session.target_yield_g / brew.yield_g)
    if brew.obviously_bad_shot:
        direction = ExtractionDirection.NO_UPDATE_BAD_SHOT
    elif estimate < session.target_time_min_s:
        direction = ExtractionDirection.FINER
    elif estimate > session.target_time_max_s:
        direction = ExtractionDirection.COARSER
    else:
        direction = ExtractionDirection.KEEP
    return ExtractionRecommendation(
        id=str(uuid4()),
        session_id=session.id,
        target_sequence=target_sequence,
        source_shot_id=source.id,
        history_through_sequence=source.sequence,
        created_at=created_at,
        target_yield_g=session.target_yield_g,
        target_time_min_s=session.target_time_min_s,
        target_time_max_s=session.target_time_max_s,
        linear_target_yield_time_s=estimate,
        direction=direction,
    )
