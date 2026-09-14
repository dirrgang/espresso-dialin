import csv
from pathlib import Path

DATASET = Path(__file__).parents[1] / "data" / "historical_shots_corrected.csv"

REQUIRED_COLUMNS = {
    "sequence",
    "bean_label",
    "grind_setting",
    "grind_macro",
    "grind_micro",
    "grind_duration_s",
    "grinder_output_g",
    "dose_correction_mode",
    "puck_dose_g",
    "brew_duration_s",
    "final_yield_g",
    "transcription_status",
    "source_region",
    "notes",
}


def _read_rows() -> list[dict[str, str]]:
    with DATASET.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_historical_dataset_has_expected_schema() -> None:
    rows = _read_rows()
    assert rows
    assert set(rows[0]) == REQUIRED_COLUMNS


def test_historical_dataset_sequence_is_unique_and_chronological() -> None:
    rows = _read_rows()
    sequence = [int(row["sequence"]) for row in rows]
    assert sequence == sorted(sequence)
    assert len(sequence) == len(set(sequence))


def test_historical_dataset_uses_explicit_missing_values() -> None:
    rows = _read_rows()
    forbidden_placeholders = {"nan", "none", "null", "?"}
    for row in rows:
        assert not ({value.strip().lower() for value in row.values()} & forbidden_placeholders)


def test_historical_dataset_controlled_vocabularies() -> None:
    rows = _read_rows()
    correction_modes = {"NONE", "TO_TARGET", "MEASURED", "UNKNOWN"}
    transcription_statuses = {"ok", "partial", "approximate"}

    assert {row["dose_correction_mode"] for row in rows} <= correction_modes
    assert {row["transcription_status"] for row in rows} <= transcription_statuses


def test_historical_dataset_uses_known_bean_identities() -> None:
    rows = _read_rows()
    assert {row["bean_label"] for row in rows[:39]} == {"cafe_intencion_espresso_intensivo"}
    assert {row["bean_label"] for row in rows[39:]} == {
        "rewe_bio_espresso_ganze_bohnen_1000g"
    }
