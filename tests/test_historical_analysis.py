import csv
from pathlib import Path
from typing import cast

import pytest

from espresso_dialin.historical import (
    FIELDS,
    audit,
    change_followups,
    chronology_rows,
    describe,
    dose_backtest,
    eligible,
    error_summary,
    exclusion_reasons,
    extraction_backtest,
    grouped_summary,
    load_shots,
    metric,
    nullable_number,
    proportional_duration,
    research_report,
    robust_flags,
    transitions,
    variability_comparison,
)

DATASET = Path(__file__).parents[1] / "data/historical_shots_corrected.csv"


def fixture_csv(tmp_path, overrides):
    base = dict(
        zip(
            FIELDS,
            [
                "1",
                "beans",
                "3E",
                "3",
                "E",
                "10",
                "20",
                "TO_TARGET",
                "18",
                "30",
                "40",
                "ok",
                "test",
                "",
            ],
            strict=True,
        )
    )
    path = tmp_path / "shots.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(base | {"sequence": str(i)} | row for i, row in enumerate(overrides, 1))
    return path


def test_current_data_and_analysis_specific_partial_rows():
    shots = load_shots(DATASET)
    with DATASET.open(encoding="utf-8", newline="") as handle:
        assert [dict(s.raw) for s in shots] == list(csv.DictReader(handle))
    assert [s.sequence for s in shots] == list(range(1, 52))
    assert shots[38].block != shots[39].block
    assert not exclusion_reasons(shots[1], "output")
    assert not exclusion_reasons(shots[1], "extraction")
    assert not exclusion_reasons(shots[25], "output")
    assert exclusion_reasons(shots[25], "extraction")
    assert exclusion_reasons(shots[13], "extraction") == ("usable_puck_dose",)
    assert len(eligible(shots, "output")) == len(eligible(shots, "setting_output"))
    assert audit(shots)["rows"] == 51


def test_derived_values_do_not_mutate_raw_or_confuse_puck(tmp_path):
    shot = load_shots(fixture_csv(tmp_path, [{}]))[0]
    before = dict(shot.raw)
    assert shot.output_rate_g_s == 2
    assert shot.t36_linear_approx_s == 27
    assert proportional_duration(shot) == 9
    assert shot.puck_group == ("approximate_target", 18)
    assert metric(shot, "grinder_output_g") == 20
    assert dict(shot.raw) == before
    with pytest.raises(TypeError):
        cast(dict[str, str], shot.raw)["grinder_output_g"] = "18"
    with pytest.raises(TypeError):
        cast(dict[str, float | None], shot.numbers)["grinder_output_g"] = 18


@pytest.mark.parametrize("value", ["", "  "])
def test_missing_number(value):
    assert nullable_number(value) is None


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "uncertain"])
def test_bad_number_not_silently_imputed(value):
    with pytest.raises(ValueError):
        nullable_number(value)


@pytest.mark.parametrize("field", ["brew_duration_s", "final_yield_g"])
@pytest.mark.parametrize("value", ["", "0", "-1"])
def test_invalid_inputs_have_no_t36(tmp_path, field, value):
    shot = load_shots(fixture_csv(tmp_path, [{field: value}]))[0]
    assert shot.t36_linear_approx_s is None
    assert exclusion_reasons(shot, "yield_pair") == (field,)
    with pytest.raises(ValueError):
        metric(shot, "t36")


@pytest.mark.parametrize("sequence", ["1", "0", "-1"])
def test_reversed_duplicate_sequence_rejected_not_sorted(tmp_path, sequence):
    with pytest.raises(ValueError, match="Sequence"):
        load_shots(fixture_csv(tmp_path, [{}, {"sequence": sequence}]))


def test_chronology_breaks_at_unknown_setting_boundary_and_sequence_gap(tmp_path):
    shots = load_shots(
        fixture_csv(
            tmp_path,
            [
                {},
                {"grind_setting": "3F"},
                {"grind_setting": ""},
                {},
                {"bean_label": "other"},
                {},
                {"sequence": "8"},
                {"sequence": "9"},
            ],
        )
    )
    pairs = transitions(shots)
    assert [(p.previous.sequence, p.current.sequence, p.changed) for p in pairs] == [
        (1, 2, True),
        (8, 9, False),
    ]
    assert shots[0].block != shots[5].block  # Reappearing bean is a new block.


@pytest.mark.parametrize(
    ("mode", "puck", "interpretation"),
    [
        ("UNKNOWN", "18", None),
        ("TO_TARGET", "", None),
        ("MEASURED", "18", "measured"),
        ("NONE", "20", "uncorrected_output"),
        ("NONE", "", "uncorrected_output"),
        ("NONE", "18", None),
    ],
)
def test_puck_semantics(tmp_path, mode, puck, interpretation):
    shot = load_shots(fixture_csv(tmp_path, [{"dose_correction_mode": mode, "puck_dose_g": puck}]))[
        0
    ]
    assert shot.puck_interpretation == interpretation


def test_past_only_prediction_and_common_target(tmp_path):
    shots = load_shots(
        fixture_csv(
            tmp_path,
            [
                {},
                {"grind_duration_s": "9", "grinder_output_g": "18"},
                {"brew_duration_s": "100"},
                {"bean_label": "other"},
            ],
        )
    )
    dose = dose_backtest(shots)
    assert dose[0]["prediction_g"] == 18
    assert dose[0]["error_g"] == 0
    rolling = extraction_backtest(shots)
    assert [row["sequence"] for row in rolling] == [2, 3]
    assert rolling[0]["raw_error_s"] == 0
    assert rolling[0]["normalized_error_s"] == 0
    assert rolling[1]["raw_error_s"] == -70
    assert all(cast(int, row["train_through"]) < cast(int, row["sequence"]) for row in rolling)
    assert extraction_backtest(shots[:2]) == rolling[:1]


def test_different_puck_targets_are_not_pooled(tmp_path):
    shots = load_shots(fixture_csv(tmp_path, [{}, {"puck_dose_g": "19"}]))
    assert extraction_backtest(shots) == []


def test_robust_summaries_flag_without_deletion(tmp_path):
    shots = load_shots(
        fixture_csv(tmp_path, [{"brew_duration_s": str(t)} for t in [29, 30, 31, 32, 90]])
    )
    assert describe([29, 30, 31, 32, 90])["median"] == 31
    assert describe([])["sd"] is None
    flags = robust_flags(shots)
    assert {row["sequence"] for row in flags if row["flag"]} == {5}
    assert all(row["n"] == 5 for row in grouped_summary(shots, "extraction"))
    constant = load_shots(fixture_csv(tmp_path, [{}] * 5))
    assert all(row["modified_z"] is None for row in robust_flags(constant))
    assert robust_flags(constant[:4]) == []


@pytest.mark.parametrize("target", [0, -1, float("inf")])
def test_invalid_dose_target(tmp_path, target):
    with pytest.raises(ValueError):
        proportional_duration(load_shots(fixture_csv(tmp_path, [{}]))[0], target)


def test_bad_schema(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("sequence,bad\n1,x\n")
    with pytest.raises(ValueError, match="schema"):
        load_shots(path)


@pytest.mark.parametrize("field", ["transcription_status", "dose_correction_mode"])
def test_unknown_vocab_requires_review(tmp_path, field):
    with pytest.raises(ValueError):
        load_shots(fixture_csv(tmp_path, [{field: "uncertain"}]))


def test_change_followups_require_immediate_repeat_and_usable_dose(tmp_path):
    shots = load_shots(
        fixture_csv(
            tmp_path,
            [
                {"grind_setting": "3D"},
                {},
                {"brew_duration_s": "34"},
                {"grind_setting": "3F", "dose_correction_mode": "UNKNOWN"},
                {"grind_setting": "3F"},
            ],
        )
    )
    followups = change_followups(shots)
    assert len(followups) == 1
    assert (followups[0]["first"], followups[0]["repeat"]) == (2, 3)
    assert followups[0]["raw_repeat_minus_first_s"] == 4
    assert followups[0]["t36_repeat_minus_first_s"] == pytest.approx(3.6)
    assert [r["sequence"] for r in chronology_rows(shots)] == [2, 3, 5]


def test_pooled_variability_uses_matched_groups_and_sample_degrees_of_freedom(tmp_path):
    shots = load_shots(
        fixture_csv(
            tmp_path,
            [
                {"brew_duration_s": "20"},
                {"brew_duration_s": "24"},
                {"grind_setting": "3F", "brew_duration_s": "50"},
                {"grind_setting": "3F", "brew_duration_s": "52"},
                {"grind_setting": "3F", "brew_duration_s": "54"},
                {"grind_setting": "3G", "brew_duration_s": "90"},
            ],
        )
    )
    raw, normalized = variability_comparison(shots)
    assert (raw["groups"], raw["n"]) == (2, 5)
    assert raw["pooled_within_sd"] == pytest.approx((16 / 3) ** 0.5)
    assert normalized["pooled_within_sd"] == pytest.approx((16 / 3) ** 0.5 * 0.9)
    assert variability_comparison(shots[:1])[0]["pooled_within_sd"] is None


def test_error_metrics_and_report(tmp_path):
    result = error_summary([{"error": -1.0}, {"error": 3.0}], "error")
    assert result == {"n": 2, "mae": 2, "rmse": 5**0.5, "median_absolute_error": 2}
    assert error_summary([], "error")["mae"] is None
    shots = load_shots(fixture_csv(tmp_path, [{}]))
    report = research_report(shots)
    audit = cast(dict[str, object], report["audit"])
    assert audit["rows"] == 1
    assert report["dose_pairs"] == []


def test_malformed_csv_row_is_rejected(tmp_path):
    path = fixture_csv(tmp_path, [{}])
    with path.open("a") as handle:
        handle.write("2,beans\n")
    with pytest.raises(ValueError, match="Malformed"):
        load_shots(path)


def test_missing_bean_excludes_grouped_analysis(tmp_path):
    shot = load_shots(fixture_csv(tmp_path, [{"bean_label": ""}]))[0]
    assert not exclusion_reasons(shot, "output")
    assert exclusion_reasons(shot, "setting_output") == ("bean_label",)
