"""Exercise the standalone export without letting acquisition migrate its source."""

import importlib.util
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
        assert first["counts"]["extraction_recommendations"] == 1
        feedback = first["tables"]["extraction_recommendations"][0]
        assert feedback["source_shot_id"] == shot.id
        assert feedback["target_sequence"] == 2
        assert raw["extraction_recommendation_id"] is None


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


@pytest.mark.parametrize("sidecars", [("-wal", "-shm"), ("-wal",), ()])
def test_inventory_rejects_wal_snapshots_without_touching_source_directory(tmp_path, sidecars):
    writer = tmp_path / "writer.sqlite3"
    Repository(writer)
    source_dir = tmp_path / "supplied"
    source_dir.mkdir()
    path = source_dir / "snapshot.sqlite3"
    with closing(sqlite3.connect(writer)) as db, db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            "INSERT INTO sessions VALUES ('wal','b','Coffee','2026-10-01T08:00:00+00:00',"
            "NULL,'Grinder','Machine',NULL,NULL,18,36,30,35,NULL)"
        )
        db.commit()
        # Copy a supplied snapshot while the writer keeps uncheckpointed evidence
        # in the WAL. Missing SHM is a legitimate supplied-snapshot shape.
        path.write_bytes(writer.read_bytes())
        for suffix in sidecars:
            Path(str(path) + suffix).write_bytes(Path(str(writer) + suffix).read_bytes())
        before = {file.name: file.read_bytes() for file in source_dir.iterdir()}
        with pytest.raises(ValueError, match="WAL-mode sources"):
            inventory.read_inventory(path)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True
        )
        assert result.returncode != 0
        assert result.stdout == ""
        assert "WAL-mode sources" in result.stderr
        assert {file.name: file.read_bytes() for file in source_dir.iterdir()} == before
