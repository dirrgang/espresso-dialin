"""Past-only grinder-output dose controllers and prospective scoring."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Protocol, Self, cast

PROVISIONAL_OUTPUT_TOLERANCE_G = 0.2


def _positive_finite(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")


def _nonnegative_finite(value: float, name: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be nonnegative and finite")


def _required_text(value: str, name: str) -> None:
    if not value:
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class DoseObservation:
    """A grinder-output observation; missing measurements remain explicit."""

    observation_id: str
    sequence: int
    bean_id: str
    session_id: str | None
    block_id: str
    grinder_setting: str
    grind_duration_s: float | None
    grinder_output_g: float | None

    def __post_init__(self) -> None:
        _required_text(self.observation_id, "observation_id")
        _required_text(self.bean_id, "bean_id")
        _required_text(self.block_id, "block_id")
        _required_text(self.grinder_setting, "grinder_setting")
        if self.sequence <= 0:
            raise ValueError("sequence must be positive")
        if self.grind_duration_s is not None:
            _positive_finite(self.grind_duration_s, "grind_duration_s")
        if self.grinder_output_g is not None:
            _positive_finite(self.grinder_output_g, "grinder_output_g")

    @property
    def output_rate_g_s(self) -> float | None:
        if self.grind_duration_s is None or self.grinder_output_g is None:
            return None
        return self.grinder_output_g / self.grind_duration_s


@dataclass(frozen=True)
class DoseTarget:
    """The context and desired output known when making a recommendation."""

    next_sequence: int
    bean_id: str
    session_id: str | None
    block_id: str
    grinder_setting: str
    target_output_g: float = 18.0
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        _required_text(self.bean_id, "bean_id")
        _required_text(self.block_id, "block_id")
        _required_text(self.grinder_setting, "grinder_setting")
        if self.next_sequence <= 0:
            raise ValueError("next_sequence must be positive")
        _positive_finite(self.target_output_g, "target_output_g")
        if self.created_at is not None and self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")


class DoseCompatibilityPolicy(Protocol):
    """Replaceable policy for deciding whether an earlier observation applies."""

    def compatible(self, observation: DoseObservation, target: DoseTarget) -> bool:
        """Return whether the observation belongs to the target's dose history."""


@dataclass(frozen=True)
class ExactDoseCompatibility:
    """Conservative initial policy: exact bean, session, block, and setting."""

    def compatible(self, observation: DoseObservation, target: DoseTarget) -> bool:
        return (
            observation.bean_id == target.bean_id
            and observation.session_id == target.session_id
            and observation.block_id == target.block_id
            and observation.grinder_setting == target.grinder_setting
        )


@dataclass(frozen=True)
class DoseRecommendation:
    """Serializable record of a prediction made before a grinder outcome exists."""

    recommendation_id: str
    created_at: datetime | None
    strategy_id: str
    model_version: str
    bean_id: str
    session_id: str | None
    block_id: str
    grinder_setting: str
    target_output_g: float
    recommended_duration_s: float
    expected_output_g: float
    estimated_rate_g_s: float
    observation_ids: tuple[str, ...]
    observation_count: int
    history_through_sequence: int

    def __post_init__(self) -> None:
        for name, value in (
            ("recommendation_id", self.recommendation_id),
            ("strategy_id", self.strategy_id),
            ("model_version", self.model_version),
            ("bean_id", self.bean_id),
            ("block_id", self.block_id),
            ("grinder_setting", self.grinder_setting),
        ):
            _required_text(value, name)
        for number_name, number_value in (
            ("target_output_g", self.target_output_g),
            ("recommended_duration_s", self.recommended_duration_s),
            ("expected_output_g", self.expected_output_g),
            ("estimated_rate_g_s", self.estimated_rate_g_s),
        ):
            _positive_finite(number_value, number_name)
        if self.created_at is not None and self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if self.observation_count <= 0 or self.observation_count != len(self.observation_ids):
            raise ValueError("observation_count must match a nonempty observation_ids tuple")
        if self.history_through_sequence <= 0:
            raise ValueError("history_through_sequence must be positive")

    def to_dict(self) -> dict[str, object]:
        return {
            "recommendation_id": self.recommendation_id,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "strategy_id": self.strategy_id,
            "model_version": self.model_version,
            "bean_id": self.bean_id,
            "session_id": self.session_id,
            "block_id": self.block_id,
            "grinder_setting": self.grinder_setting,
            "target_output_g": self.target_output_g,
            "recommended_duration_s": self.recommended_duration_s,
            "expected_output_g": self.expected_output_g,
            "estimated_rate_g_s": self.estimated_rate_g_s,
            "observation_ids": list(self.observation_ids),
            "observation_count": self.observation_count,
            "history_through_sequence": self.history_through_sequence,
        }

    def to_json(self) -> str:
        """Return stable compact JSON suitable for later persistence."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Self:
        created = value["created_at"]
        observation_ids = value["observation_ids"]
        if created is not None and not isinstance(created, str):
            raise ValueError("created_at must be an ISO string or null")
        if not isinstance(observation_ids, list) or not all(
            isinstance(item, str) for item in observation_ids
        ):
            raise ValueError("observation_ids must be a list of strings")
        return cls(
            recommendation_id=str(value["recommendation_id"]),
            created_at=datetime.fromisoformat(created) if created is not None else None,
            strategy_id=str(value["strategy_id"]),
            model_version=str(value["model_version"]),
            bean_id=str(value["bean_id"]),
            session_id=(str(value["session_id"]) if value["session_id"] is not None else None),
            block_id=str(value["block_id"]),
            grinder_setting=str(value["grinder_setting"]),
            target_output_g=float(cast(str | int | float, value["target_output_g"])),
            recommended_duration_s=float(cast(str | int | float, value["recommended_duration_s"])),
            expected_output_g=float(cast(str | int | float, value["expected_output_g"])),
            estimated_rate_g_s=float(cast(str | int | float, value["estimated_rate_g_s"])),
            observation_ids=tuple(observation_ids),
            observation_count=int(cast(str | int | float, value["observation_count"])),
            history_through_sequence=int(
                cast(str | int | float, value["history_through_sequence"])
            ),
        )


class InsufficientDoseHistoryError(ValueError):
    """No earlier compatible observation has both required measurements."""


class DoseController(Protocol):
    @property
    def strategy_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def recommend(
        self, target: DoseTarget, observations: Sequence[DoseObservation]
    ) -> DoseRecommendation:
        """Make a recommendation using observations strictly before the target."""


def _compatible_history(
    target: DoseTarget,
    observations: Sequence[DoseObservation],
    policy: DoseCompatibilityPolicy,
) -> tuple[DoseObservation, ...]:
    return tuple(
        sorted(
            (
                observation
                for observation in observations
                if observation.sequence < target.next_sequence
                and policy.compatible(observation, target)
                and observation.output_rate_g_s is not None
            ),
            key=lambda observation: (observation.sequence, observation.observation_id),
        )
    )


def _recommendation_id(
    strategy_id: str, model_version: str, target: DoseTarget, history: Sequence[DoseObservation]
) -> str:
    payload = {
        "strategy_id": strategy_id,
        "model_version": model_version,
        "next_sequence": target.next_sequence,
        "bean_id": target.bean_id,
        "session_id": target.session_id,
        "block_id": target.block_id,
        "grinder_setting": target.grinder_setting,
        "target_output_g": target.target_output_g,
        "observation_ids": [observation.observation_id for observation in history],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"dose-{digest[:24]}"


def _build_recommendation(
    controller: DoseController,
    target: DoseTarget,
    history: Sequence[DoseObservation],
    rate_g_s: float,
) -> DoseRecommendation:
    _positive_finite(rate_g_s, "estimated_rate_g_s")
    duration = target.target_output_g / rate_g_s
    return DoseRecommendation(
        recommendation_id=_recommendation_id(
            controller.strategy_id, controller.model_version, target, history
        ),
        created_at=target.created_at,
        strategy_id=controller.strategy_id,
        model_version=controller.model_version,
        bean_id=target.bean_id,
        session_id=target.session_id,
        block_id=target.block_id,
        grinder_setting=target.grinder_setting,
        target_output_g=target.target_output_g,
        recommended_duration_s=duration,
        expected_output_g=rate_g_s * duration,
        estimated_rate_g_s=rate_g_s,
        observation_ids=tuple(observation.observation_id for observation in history),
        observation_count=len(history),
        history_through_sequence=max(observation.sequence for observation in history),
    )


@dataclass(frozen=True)
class LastShotProportionalController:
    """Use the rate from the most recent earlier compatible observation."""

    compatibility: DoseCompatibilityPolicy = field(default_factory=ExactDoseCompatibility)
    strategy_id: str = "last-shot-proportional"
    model_version: str = "1"

    def recommend(
        self, target: DoseTarget, observations: Sequence[DoseObservation]
    ) -> DoseRecommendation:
        compatible = _compatible_history(target, observations, self.compatibility)
        if not compatible:
            raise InsufficientDoseHistoryError("no earlier compatible dose observation")
        last = compatible[-1]
        rate = last.output_rate_g_s
        assert rate is not None
        return _build_recommendation(self, target, (last,), rate)


@dataclass(frozen=True)
class MedianRateController:
    """Use the median output rate from all earlier compatible observations."""

    compatibility: DoseCompatibilityPolicy = field(default_factory=ExactDoseCompatibility)
    strategy_id: str = "past-only-median-rate"
    model_version: str = "1"

    def recommend(
        self, target: DoseTarget, observations: Sequence[DoseObservation]
    ) -> DoseRecommendation:
        compatible = _compatible_history(target, observations, self.compatibility)
        if not compatible:
            raise InsufficientDoseHistoryError("no earlier compatible dose observation")
        rates = [observation.output_rate_g_s for observation in compatible]
        rate = median(rate for rate in rates if rate is not None)
        return _build_recommendation(self, target, compatible, rate)


@dataclass(frozen=True)
class DoseRecommendationScore:
    """Score the stored rate prediction at the action actually taken."""

    recommendation_id: str
    actual_duration_s: float
    actual_output_g: float
    predicted_output_g: float
    signed_error_g: float
    absolute_error_g: float
    target_tolerance_g: float
    within_target_tolerance: bool


def score_recommendation(
    recommendation: DoseRecommendation,
    *,
    actual_duration_s: float,
    actual_output_g: float,
    target_tolerance_g: float = PROVISIONAL_OUTPUT_TOLERANCE_G,
) -> DoseRecommendationScore:
    """Score without refitting; signed error is prediction minus actual output."""
    _positive_finite(actual_duration_s, "actual_duration_s")
    _positive_finite(actual_output_g, "actual_output_g")
    _nonnegative_finite(target_tolerance_g, "target_tolerance_g")
    predicted = recommendation.estimated_rate_g_s * actual_duration_s
    error = predicted - actual_output_g
    return DoseRecommendationScore(
        recommendation_id=recommendation.recommendation_id,
        actual_duration_s=actual_duration_s,
        actual_output_g=actual_output_g,
        predicted_output_g=predicted,
        signed_error_g=error,
        absolute_error_g=abs(error),
        target_tolerance_g=target_tolerance_g,
        within_target_tolerance=(
            abs(actual_output_g - recommendation.target_output_g) <= target_tolerance_g
        ),
    )
