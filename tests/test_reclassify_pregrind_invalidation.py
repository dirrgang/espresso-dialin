import json
import sqlite3
from contextlib import closing
from importlib.util import module_from_spec, spec_from_file_location
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

SCRIPT = Path(__file__).parents[1] / "scripts" / "reclassify_pregrind_invalidation.py"
SPEC = spec_from_file_location("reclassify_pregrind_invalidation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
repair = module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def invalidated_pregrind(tmp_path):
    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(
        Session(id="session", bean_id="bean", bean_name="Coffee", started_at=utc_now())
    )
    shot = Acquisition(repo).freeze("session", "4E", 1, "manual", 10.3)
    repo.resolve(shot.id, ShotStatus.INVALIDATED, "Wrong selection.")
    return repo, shot


def test_default_cli_dry_run_does_not_mutate(tmp_path, monkeypatch, capsys):
    repo, shot = invalidated_pregrind(tmp_path)
    before = repo.shots("session")[0]
    monkeypatch.setattr(
        "sys.argv",
        [
            "reclassify_pregrind_invalidation.py",
            str(repo.path),
            "--session-id",
            "session",
            "--shot-id",
            shot.id,
        ],
    )
    repair.main()
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "dry-run"
    assert output["candidate"]["resolution_status"] == "INVALIDATED"
    assert Repository(repo.path).shots("session")[0] == before
    assert not list(tmp_path.glob("*.pregrind-repair-*.sqlite3"))


def test_apply_backs_up_then_reclassifies_with_auditable_original_metadata(tmp_path):
    repo, shot = invalidated_pregrind(tmp_path)
    original = repo.shots("session")[0].resolution
    backup, corrected = repair.apply_repair(
        repo.path,
        "session",
        shot.id,
        confirmed_no_physical_grinding=True,
    )
    assert backup.exists()
    assert corrected["resolution_status"] == "ABANDONED"
    assert corrected["resolution_recorded_at"] == original.recorded_at.isoformat()
    assert "status=INVALIDATED" in corrected["resolution_reason"]
    assert original.recorded_at.isoformat() in corrected["resolution_reason"]
    assert json.dumps(original.reason) in corrected["resolution_reason"]

    with closing(sqlite3.connect(backup)) as db:
        assert db.execute(
            "SELECT status, recorded_at, reason FROM shot_resolutions WHERE shot_id=?",
            (shot.id,),
        ).fetchone() == ("INVALIDATED", original.recorded_at.isoformat(), original.reason)
    with closing(sqlite3.connect(repo.path)) as db:
        trigger = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='resolution_update'"
        ).fetchone()
        assert trigger is not None
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE shot_resolutions SET reason='changed' WHERE shot_id=?", (shot.id,))


def test_apply_requires_explicit_physical_confirmation(tmp_path):
    repo, shot = invalidated_pregrind(tmp_path)
    with pytest.raises(ValueError, match="explicit confirmation"):
        repair.apply_repair(
            repo.path,
            "session",
            shot.id,
            confirmed_no_physical_grinding=False,
        )
    assert repo.shots("session")[0].status == ShotStatus.INVALIDATED
    assert not list(tmp_path.glob("*.pregrind-repair-*.sqlite3"))


@pytest.mark.parametrize("evidence", ["grinding", "brew"])
def test_repair_rejects_any_physical_evidence(tmp_path, evidence):
    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(
        Session(id="session", bean_id="bean", bean_name="Coffee", started_at=utc_now())
    )
    shot = Acquisition(repo).freeze("session", "4E", 1, "manual", 10.3)
    repo.save_grinding(
        shot.id,
        GrindingResult(
            setting="4E",
            duration_s=10.3,
            output_g=19.65,
            correction=CorrectionMode.TO_TARGET,
        ),
    )
    if evidence == "brew":
        repo.complete(shot.id, BrewingResult(duration_s=57, yield_g=35.43))
    repo.resolve(shot.id, ShotStatus.INVALIDATED, "Evidence is uncertain")
    with pytest.raises(ValueError, match="physical evidence"):
        repair.inspect_target(repo.path, "session", shot.id)
    assert repo.shots("session")[0].status == ShotStatus.INVALIDATED


def test_repair_rejects_non_invalidated_resolution_and_unexpected_trigger(tmp_path):
    repo, shot = invalidated_pregrind(tmp_path)
    with closing(sqlite3.connect(repo.path)) as db, db:
        db.execute("DROP TRIGGER resolution_update")
        db.execute(
            "CREATE TRIGGER resolution_update BEFORE UPDATE ON shot_resolutions "
            "BEGIN SELECT RAISE(ABORT, 'different guard'); END"
        )
    with pytest.raises(ValueError, match="definition"):
        repair.inspect_target(repo.path, "session", shot.id)

    other = Repository(tmp_path / "other.sqlite3")
    other.add_session(
        Session(id="session", bean_id="bean", bean_name="Coffee", started_at=utc_now())
    )
    abandoned = Acquisition(other).freeze("session", "4E", 1, "manual", 10.3)
    other.resolve(abandoned.id, ShotStatus.ABANDONED, "No physical grinding occurred")
    with pytest.raises(ValueError, match="not currently INVALIDATED"):
        repair.inspect_target(other.path, "session", abandoned.id)


def test_apply_failure_rolls_back_resolution_and_trigger(tmp_path, monkeypatch):
    repo, shot = invalidated_pregrind(tmp_path)
    original_check = repair._verified_trigger_sql
    calls = 0

    def fail_after_trigger_restore(db):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise RuntimeError("injected post-update failure")
        return original_check(db)

    monkeypatch.setattr(repair, "_verified_trigger_sql", fail_after_trigger_restore)
    with pytest.raises(RuntimeError, match="injected"):
        repair.apply_repair(
            repo.path,
            "session",
            shot.id,
            confirmed_no_physical_grinding=True,
        )
    assert Repository(repo.path).shots("session")[0].status == ShotStatus.INVALIDATED
    with closing(sqlite3.connect(repo.path)) as db:
        assert db.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='resolution_update'"
        ).fetchone()
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
