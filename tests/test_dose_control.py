import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from espresso_dialin.dose_control import (
    DoseObservation,
    DoseRecommendation,
    DoseTarget,
    InsufficientDoseHistoryError,
    LastShotProportionalController,
    MedianRateController,
    score_recommendation,
)
from espresso_dialin.historical import load_shots, rolling_dose_backtest, rolling_dose_report

DATASET = Path(__file__).parents[1] / "data" / "historical_shots_staging.csv"


def observation(
    sequence: int,
    *,
    duration: float | None = 10.0,
    output: float | None = 20.0,
    bean: str = "bean-a",
    session: str | None = "session-a",
    block: str = "block-a",
    setting: str = "3E",
) -> DoseObservation:
    return DoseObservation(
        observation_id=f"shot-{sequence}",
        sequence=sequence,
        bean_id=bean,
        session_id=session,
        block_id=block,
        grinder_setting=setting,
        grind_duration_s=duration,
        grinder_output_g=output,
    )


def target(**changes: object) -> DoseTarget:
    values: dict[str, object] = {
        "next_sequence": 4,
        "bean_id": "bean-a",
        "session_id": "session-a",
        "block_id": "block-a",
        "grinder_setting": "3E",
        "target_output_g": 18.0,
        "created_at": datetime(2026, 9, 11, 8, 30, tzinfo=UTC),
    }
    values.update(changes)
    return DoseTarget(**values)  # type: ignore[arg-type]


def test_last_shot_proportional_formula_uses_only_latest_compatible_observation():
    result = LastShotProportionalController().recommend(
        target(), [observation(1, duration=8, output=16), observation(3, duration=10, output=20)]
    )
    assert result.recommended_duration_s == 9
    assert result.expected_output_g == 18
    assert result.estimated_rate_g_s == 2
    assert result.observation_ids == ("shot-3",)
    assert result.observation_count == 1
    assert result.history_through_sequence == 3


def test_median_rate_formula_uses_all_past_compatible_observations():
    result = MedianRateController().recommend(
        target(),
        [
            observation(1, duration=10, output=10),
            observation(2, duration=10, output=20),
            observation(3, duration=10, output=30),
        ],
    )
    assert result.estimated_rate_g_s == 2
    assert result.recommended_duration_s == 9
    assert result.observation_ids == ("shot-1", "shot-2", "shot-3")
    assert result.observation_count == 3


@pytest.mark.parametrize(
    ("field", "different"),
    [
        ("bean_id", "bean-b"),
        ("session_id", "session-b"),
        ("block_id", "block-b"),
        ("grinder_setting", "3F"),
    ],
)
def test_exact_compatibility_isolates_every_context_dimension(field, different):
    incompatible = replace(observation(3), **{field: different})
    with pytest.raises(InsufficientDoseHistoryError):
        LastShotProportionalController().recommend(target(), [incompatible])


def test_missing_measurements_are_ignored_and_one_valid_observation_is_sufficient():
    observations = [
        observation(1, duration=None),
        observation(2, output=None),
        observation(3, duration=9, output=18),
    ]
    result = MedianRateController().recommend(target(), observations)
    assert result.observation_ids == ("shot-3",)
    assert result.recommended_duration_s == 9


def test_insufficient_history_is_explicit():
    with pytest.raises(InsufficientDoseHistoryError):
        MedianRateController().recommend(target(), [observation(1, output=None)])


@pytest.mark.parametrize("field", ["grind_duration_s", "grinder_output_g"])
@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_observation_measurements_are_rejected(field, value):
    with pytest.raises(ValueError, match="positive and finite"):
        replace(observation(1), **{field: value})


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_target_is_rejected(value):
    with pytest.raises(ValueError, match="positive and finite"):
        target(target_output_g=value)


def test_sequences_identity_and_timestamp_are_validated():
    with pytest.raises(ValueError, match="sequence"):
        replace(observation(1), sequence=0)
    with pytest.raises(ValueError, match="bean_id"):
        replace(observation(1), bean_id="")
    with pytest.raises(ValueError, match="next_sequence"):
        target(next_sequence=0)
    with pytest.raises(ValueError, match="timezone-aware"):
        target(created_at=datetime(2026, 9, 11))


def test_compatibility_policy_can_be_replaced_without_changing_controller():
    class SameBeanPolicy:
        def compatible(self, candidate, requested):
            return candidate.bean_id == requested.bean_id

    result = LastShotProportionalController(compatibility=SameBeanPolicy()).recommend(
        target(), [observation(1, session="other", block="other", setting="other")]
    )
    assert result.observation_ids == ("shot-1",)


def test_future_observations_never_leak_into_recommendation():
    past_only = MedianRateController().recommend(target(), [observation(1, output=10)])
    with_future = MedianRateController().recommend(
        target(),
        [observation(1, output=10), observation(4, output=100), observation(5, output=100)],
    )
    assert with_future == past_only


def test_recommendation_serialization_is_deterministic_and_round_trips():
    result = MedianRateController().recommend(target(), [observation(1), observation(2)])
    assert result.to_json() == result.to_json()
    assert json.loads(result.to_json())["observation_ids"] == ["shot-1", "shot-2"]
    assert DoseRecommendation.from_dict(result.to_dict()) == result
    assert (
        MedianRateController()
        .recommend(target(), [observation(1), observation(2)])
        .recommendation_id
        == result.recommendation_id
    )


def test_recommendation_deserialization_rejects_wrong_structural_types():
    result = MedianRateController().recommend(target(), [observation(1)])
    bad_timestamp = result.to_dict() | {"created_at": 123}
    bad_ids = result.to_dict() | {"observation_ids": "shot-1"}
    with pytest.raises(ValueError, match="created_at"):
        DoseRecommendation.from_dict(bad_timestamp)
    with pytest.raises(ValueError, match="observation_ids"):
        DoseRecommendation.from_dict(bad_ids)
    with pytest.raises(ValueError, match="observation_count"):
        replace(result, observation_count=0)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(result, created_at=datetime(2026, 9, 11))
    with pytest.raises(ValueError, match="history_through_sequence"):
        replace(result, history_through_sequence=0)


def test_recommendation_scoring_uses_actual_action_without_refitting():
    recommendation = LastShotProportionalController().recommend(target(), [observation(1)])
    score = score_recommendation(
        recommendation, actual_duration_s=8.5, actual_output_g=17.8, target_tolerance_g=0.25
    )
    assert score.predicted_output_g == 17
    assert score.signed_error_g == pytest.approx(-0.8)
    assert score.absolute_error_g == pytest.approx(0.8)
    assert score.within_target_tolerance
    assert recommendation.estimated_rate_g_s == 2  # Scoring did not update the record.
    assert score_recommendation(
        recommendation, actual_duration_s=9, actual_output_g=18, target_tolerance_g=0
    ).within_target_tolerance
    with pytest.raises(ValueError, match="nonnegative"):
        score_recommendation(
            recommendation, actual_duration_s=9, actual_output_g=18, target_tolerance_g=-0.1
        )


def test_historical_rolling_evaluation_is_past_only_and_separates_action_from_prediction():
    shots = load_shots(DATASET)
    rows = rolling_dose_backtest(shots)
    assert rows
    assert {row["strategy_id"] for row in rows} == {
        "last-shot-proportional",
        "past-only-median-rate",
    }
    assert all(row["train_through"] < row["sequence"] for row in rows)
    assert all(row["prediction_g"] != row["recommended_duration_s"] for row in rows)
    assert rolling_dose_backtest(shots[:25]) == [row for row in rows if row["sequence"] <= 25]

    report = rolling_dose_report(shots)
    assert report["overall"]["last-shot-proportional"]["n"] > 0
    assert set(report["by_block"]) == {"historical-block-0", "historical-block-1"}
    assert rolling_dose_backtest(shots, controllers=[]) == []
