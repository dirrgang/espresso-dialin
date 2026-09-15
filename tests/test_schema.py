"""Migrate actual legacy schemas and populated evidence without inventing semantics."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from espresso_dialin import schema
from espresso_dialin.application import Acquisition
from espresso_dialin.domain import ShotStatus
from espresso_dialin.dose_control import DoseObservation, DoseTarget, MedianRateController
from espresso_dialin.repository import Repository


@pytest.fixture
def v1_path(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    source = Path(__file__).parent / "fixtures" / "schema_v1.sql"
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(source.read_text(encoding="utf-8"))
        for sid in ("one", "two"):
            db.execute(
                "INSERT INTO sessions VALUES (?, 'bean', 'Coffee', "
                "'2026-09-01T08:00:00+00:00', NULL, 'Grinder', 'Machine', "
                "'Roaster', '2026-08-01', 18, 36, 30, 35)",
                (sid,),
            )
        model = MedianRateController().recommend(
            DoseTarget(
                next_sequence=2,
                bean_id="bean",
                session_id="one",
                block_id="one:1",
                grinder_setting="3E",
                created_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
            ),
            [
                DoseObservation(
                    observation_id="shot-1",
                    sequence=1,
                    bean_id="bean",
                    session_id="one",
                    block_id="one:1",
                    grinder_setting="3E",
                    grind_duration_s=9.7,
                    grinder_output_g=20,
                )
            ],
        )
        assert model.created_at is not None
        for rid, sid, seq, created, prediction in (
            ("manual-1", "one", 1, "2026-09-01T08:01:00+00:00", None),
            (model.recommendation_id, "one", 2, model.created_at.isoformat(), model),
            ("manual-2", "two", 1, "2026-09-01T08:01:00+00:00", None),
        ):
            db.execute(
                "INSERT INTO recommendations VALUES (?, ?, ?, ?, '3E', ?, 18, ?, '1', ?, ?, ?, 1)",
                (
                    rid,
                    sid,
                    seq,
                    created,
                    prediction.recommended_duration_s if prediction else 9.74,
                    prediction.strategy_id if prediction else "manual",
                    prediction.estimated_rate_g_s if prediction else None,
                    prediction.expected_output_g if prediction else None,
                    prediction.to_json() if prediction else None,
                ),
            )
            db.execute(
                "INSERT INTO shots (id,session_id,sequence,created_at,selected_recommendation_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"shot-{seq}" if sid == "one" else "shot-empty", sid, seq, created, rid),
            )
            if sid == "one":
                db.execute(
                    "UPDATE shots SET actual_setting='3E',actual_duration_s=9.7,"
                    "grinder_output_g=20, correction='TO_TARGET' WHERE id=?",
                    (f"shot-{seq}",),
                )
                if seq == 1:
                    db.execute(
                        "UPDATE shots SET brew_duration_s=32,final_yield_g=36.8,"
                        "purged_before_shot=1, obviously_bad_shot=1,notes='kept raw',"
                        "completed_at='2026-09-01T08:05:00+00:00' "
                        "WHERE id='shot-1'"
                    )
    return path


@pytest.fixture
def v2_ambiguous_pregrind_path(tmp_path):
    path = tmp_path / "legacy-v2.sqlite3"
    with closing(sqlite3.connect(path)) as db, db:
        schema._execute_schema(db, schema.FRESH_SCHEMA)
        schema._execute_schema(db, schema.LIFECYCLE_SCHEMA_V2)
        db.execute("PRAGMA user_version = 2")
        db.execute(
            "INSERT INTO sessions VALUES "
            "('s','b','Coffee','2026-09-01T08:00:00+00:00',NULL,'Grinder','Machine',"
            "NULL,NULL,18,36,30,35,NULL)"
        )
        for sequence, rid, created in (
            (1, "r1", "2026-09-01T08:01:00+00:00"),
            (2, "r2", "2026-09-01T08:10:00+00:00"),
        ):
            db.execute(
                "INSERT INTO recommendations VALUES "
                "(?, 's', ?, ?, '3E', 9.7, 18, 'manual', '1', NULL, NULL, NULL, 1)",
                (rid, sequence, created),
            )
            db.execute(
                "INSERT INTO shots (id,session_id,sequence,created_at,selected_recommendation_id) "
                "VALUES (?, 's', ?, ?, ?)",
                (f"shot-{sequence}", sequence, created, rid),
            )
            if sequence == 1:
                db.execute(
                    "UPDATE shots SET actual_setting='3E', actual_duration_s=9.7, "
                    "grinder_output_g=18, correction='TO_TARGET', "
                    "grinding_recorded_at='2026-09-01T08:02:00+00:00', "
                    "brew_duration_s=32, final_yield_g=36, "
                    "completed_at='2026-09-01T08:03:00+00:00' WHERE id='shot-1'"
                )
        db.execute(
            "INSERT INTO shot_resolutions VALUES "
            "('shot-2','ABANDONED','2026-09-01T08:11:00+00:00','No reliable grinding result')"
        )
    return path


def snapshot(path):
    with closing(sqlite3.connect(path)) as db:
        return {
            table: (
                tuple(r[1] for r in db.execute(f"PRAGMA table_info({table})")),
                db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall(),
            )
            for table in ("sessions", "shots", "recommendations")
        }


def test_v1_migration_preserves_every_original_value_and_unknown_times(v1_path):
    before = snapshot(v1_path)
    repo = Repository(v1_path)
    with closing(sqlite3.connect(v1_path)) as db:
        for table, (columns, rows) in before.items():
            assert (
                db.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY id").fetchall()
                == rows
            )
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert all(session.bag_opened_date is None for session in repo.sessions())
    complete, pending = repo.shots("one")
    assert complete.status == ShotStatus.COMPLETED
    assert complete.brewing_recorded_at == complete.completed_at
    assert complete.plan_frozen_at == complete.created_at
    assert complete.grinding_recorded_at is None
    assert pending.status == ShotStatus.PENDING_BREWING and pending.grinding_recorded_at is None
    assert repo.shots("two")[0].status == ShotStatus.PENDING_GRINDING
    migrated_model = repo.plans("one", 2)[0].model
    assert migrated_model is not None and len(migrated_model.observation_ids) == 1
    after = snapshot(v1_path)
    Repository(v1_path)
    assert snapshot(v1_path) == after
    repo.resolve(pending.id, ShotStatus.ABANDONED, "Legacy brew abandoned; grinder result valid")
    plans = Acquisition(repo).preview("one", "3E").plans
    models = tuple(p.model for p in plans if p.model is not None)
    assert len(models) == len(plans)
    assert {model.observation_ids for model in models} == {("shot-2",), ("shot-1", "shot-2")}
    assert Acquisition(repo).freeze("one", "3E", 3, "past-only-median-rate").pending


def test_v2_migration_keeps_ambiguous_pregrind_abandonment_conservative(
    v2_ambiguous_pregrind_path,
):
    repo = Repository(v2_ambiguous_pregrind_path)
    with closing(sqlite3.connect(v2_ambiguous_pregrind_path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        columns = {row[1] for row in db.execute("PRAGMA table_info(shot_resolutions)")}
        assert "no_physical_grinding_confirmed" in columns
        assert db.execute(
            "SELECT no_physical_grinding_confirmed FROM shot_resolutions WHERE shot_id='shot-2'"
        ).fetchone() == (None,)
    legacy = repo.shots("s")[1]
    assert legacy.resolution is not None
    assert legacy.resolution.no_physical_grinding_confirmed is None
    assert not Acquisition(repo).preview("s", "3E").plans


def test_migration_failure_rolls_back_ddl_data_and_version(v1_path, monkeypatch):
    before = snapshot(v1_path)
    original = schema._execute_schema

    def fail_after_ddl(db, script):
        original(db, script)
        raise sqlite3.OperationalError("injected failure after migration DDL")

    with monkeypatch.context() as patch:
        patch.setattr(schema, "_execute_schema", fail_after_ddl)
        with pytest.raises(sqlite3.OperationalError, match="injected failure"):
            Repository(v1_path)
    assert snapshot(v1_path) == before
    with closing(sqlite3.connect(v1_path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='one_pending_shot'"
        ).fetchone()
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='shot_resolutions'"
        ).fetchone()
    Repository(v1_path)


def test_fresh_schema_does_not_run_legacy_migration(tmp_path, monkeypatch):
    def unexpected_v1_migration(db):
        pytest.fail("fresh databases must be created directly at v3")

    def unexpected_v2_migration(db):
        pytest.fail("fresh databases must be created directly at v3")

    monkeypatch.setattr(schema, "migrate_v1_to_v2", unexpected_v1_migration)
    monkeypatch.setattr(schema, "migrate_v2_to_v3", unexpected_v2_migration)
    repo = Repository(tmp_path / "fresh.sqlite3")
    assert repo.sessions() == []
    with closing(sqlite3.connect(repo.path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3


def test_app_launch_migrates_v1_and_shows_pending_phase(v1_path, monkeypatch):
    monkeypatch.setenv("ESPRESSO_DIALIN_DB", str(v1_path))
    app = AppTest.from_file(str(Path(__file__).parents[1] / "streamlit_app.py")).run()
    assert not app.exception and not app.error
    with closing(sqlite3.connect(v1_path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
    app.selectbox(key="current_session").select("one").run()
    assert not app.exception and not app.error
    assert any(input.label == "Brew duration (s)" for input in app.number_input)
    assert any(button.label == "Confirm shot resolution" for button in app.button)
