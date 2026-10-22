"""Exercise the standalone export without letting acquisition migrate its source."""

import importlib.util
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from espresso_dialin.application import Acquisition
from espresso_dialin.domain import (
    BrewingResult,
    CorrectionMode,
    GrindingResult,
    Session,
    ShotStatus,
    utc_now,
)
from espresso_dialin.repository import Repository

SCRIPT = Path(__file__).parents[1] / "scripts" / "inventory_prospective.py"
spec = importlib.util.spec_from_file_location("inventory_prospective", SCRIPT)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def test_inventory_preserves_populated_source_and_raw_nulls(tmp_path):
    path = tmp_path / "live.sqlite3"
    repo = Repository(path)
    repo.add_session(Session(id="s", bean_id="b", bean_name="Coffee", started_at=utc_now()))
    shot = Acquisition(repo).freeze("s", "opaque", 1, "manual", 10)
    repo.save_grinding(
        shot.id,
        GrindingResult(
            setting="opaque",
            duration_s=9,
            output_g=16.4,
            correction=CorrectionMode.MEASURED,
            puck_dose_g=17.8,
        ),
    )
    repo.complete(shot.id, BrewingResult(duration_s=28, yield_g=37))
    repo.resolve(shot.id, ShotStatus.INVALIDATED, "Synthetic entry error")
    before = path.read_bytes()
    first = inventory.read_inventory(path)
    second = inventory.read_inventory(path)
    assert path.read_bytes() == before
    assert first["logical_snapshot_sha256"] == second["logical_snapshot_sha256"]
    assert first["quick_check"] == ["ok"] and first["foreign_key_errors"] == []
    assert first["counts"]["sessions"] == 1 and first["counts"]["shots"] == 1
    assert first["tables"]["sessions"][0]["roast_date"] is None
    raw = first["tables"]["shots"][0]
    assert raw["sequence"] == 1 and raw["intent"] == "ASSISTED"
    assert raw["actual_duration_s"] == 9 and raw["puck_dose_g"] == 17.8
    assert raw["experiment_step_id"] is None
    assert raw["selected_recommendation_id"] == shot.selected_recommendation_id
    assert first["tables"]["shot_resolutions"][0]["reason"] == "Synthetic entry error"
    if first["schema_version"] == 4:
        assert "extraction_recommendations" not in first["counts"]
    else:
        assert first["counts"]["extraction_recommendations"] == 0


def test_inventory_missing_and_unsupported_sources_do_not_create_or_migrate(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError):
        inventory.read_inventory(path)
    assert not path.exists()
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA user_version=3")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="no migration performed"):
        inventory.read_inventory(path)
    assert path.read_bytes() == before


def test_inventory_cli_reads_committed_wal_rows(tmp_path):
    path = tmp_path / "live.sqlite3"
    Repository(path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("PRAGMA journal_mode=WAL")
        # Keep the writer open so the latest committed row remains in the WAL.
        db.execute(
            "INSERT INTO sessions VALUES ('wal','b','Coffee','2026-10-01T08:00:00+00:00',"
            "NULL,'Grinder','Machine',NULL,NULL,18,36,30,35,NULL)"
        )
        db.commit()
        before = path.read_bytes()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(path)], check=True, capture_output=True, text=True
        )
        assert json.loads(result.stdout)["tables"]["sessions"][0]["id"] == "wal"
        assert path.read_bytes() == before
