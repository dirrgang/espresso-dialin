"""Prospective design, persistence, lifecycle, and raw export guarantees."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from espresso_dialin import schema
from espresso_dialin.application import Acquisition
from espresso_dialin.domain import (
    BrewingResult,
    CorrectionMode,
    GrindingResult,
    Session,
    ShotIntent,
    ShotStatus,
    utc_now,
)
from espresso_dialin.experiments import ExperimentFamily, build_experiment
from espresso_dialin.repository import Repository


@pytest.fixture
def repo(tmp_path):
    repo = Repository(tmp_path / "experiments.sqlite3")
    repo.add_session(
        Session(id="s", bean_id="b", bean_name="Coffee", started_at=utc_now() - timedelta(hours=1))
    )
    return repo


def design(**kwargs):
    return build_experiment(
        "s",
        kwargs.pop("family", ExperimentFamily.REPLICATION),
        "opaque-setting",
        9.5,
        18,
        question="Within-condition variability?",
        **kwargs,
    )


def grind(repo, shot, setting="opaque-setting", duration=9.5, note=""):
    repo.save_grinding(
        shot.id,
        GrindingResult(
            setting=setting,
            duration_s=duration,
            output_g=18.2,
            correction=CorrectionMode.TO_TARGET,
            deviation_note=note,
        ),
    )


def finish(repo, shot):
    grind(repo, shot)
    repo.complete(shot.id, BrewingResult(duration_s=32, yield_g=36.5))


def test_designs_are_bounded_balanced_and_predefined():
    fixed = design()
    assert len(fixed.steps) == 3 and fixed.estimated_coffee_g == 54
    assert [s.replicate for s in fixed.steps] == [1, 2, 3]
    response = design(family=ExperimentFamily.DURATION)
    assert [s.duration_s for s in response.steps] == [9.5, 9, 10, 9.5, 10, 9, 9.5]
    assert response.estimated_coffee_g == pytest.approx(126)
    assert response.steps[-1].reference_sequence == 1
    assert {s.setting for s in response.steps} == {"opaque-setting"}
    for condition in ("low", "high", "reference"):
        positions = [s.sequence for s in response.steps if s.condition == condition]
        assert sum(positions) / len(positions) == 4


@pytest.mark.parametrize(
    "kwargs",
    [
        {"replicates": 2},
        {"replicates": 7},
        {"family": "unknown"},
        {"family": ExperimentFamily.DURATION, "delta_s": 0},
        {"family": ExperimentFamily.DURATION, "delta_s": 9.5},
    ],
)
def test_invalid_design_request(kwargs):
    with pytest.raises(ValueError):
        design(**kwargs)


@pytest.mark.parametrize(
    "change",
    [
        {"sequence": 0},
        {"replicate": 0},
        {"reference_sequence": 0},
        {"reference_sequence": 1},
        {"duration_s": float("nan")},
        {"setting": " "},
    ],
)
def test_step_validation(change):
    with pytest.raises(ValueError):
        replace(design().steps[0], **change)


def test_design_consistency_validation():
    e = design()
    for changes in (
        {"family": "unknown"},
        {"steps": ()},
        {"steps": (e.steps[1],)},
        {"steps": (e.steps[0], replace(e.steps[1], id=e.steps[0].id), e.steps[2])},
        {"steps": (e.steps[0], replace(e.steps[1], duration_s=10), e.steps[2])},
        {"steps": (e.steps[0], replace(e.steps[1], replicate=3), e.steps[2])},
        {
            "steps": (
                e.steps[0],
                replace(e.steps[1], condition="other", replicate=1, duration_s=10),
                e.steps[2],
            )
        },
    ):
        with pytest.raises(ValueError):
            replace(e, **changes)


def test_experiment_restart_progress_and_raw_export(repo):
    e = design()
    repo.add_experiment(e)
    assert repo.experiments("s") == [e]
    assert not repo.shots("s")
    p = repo.experiment_progress(e.id)
    assert p.status == "READY" and p.finished == p.completed == 0
    assert p.observations[0].deviations == ()
    app = Acquisition(repo)
    for index, step in enumerate(e.steps):
        shot = app.freeze_experiment_step(e.id, step.id)
        assert shot.intent == ShotIntent.EXPERIMENT and shot.experiment_step_id == step.id
        assert repo.experiment_progress(e.id).next_step is None
        if index == 0:
            grind(repo, shot, setting="actual-other", duration=9.7, note="operator override")
            repo.complete(shot.id, BrewingResult(duration_s=33, yield_g=37))
        else:
            finish(repo, shot)
        repo = Repository(repo.path)
        app = Acquisition(repo)
        p = repo.experiment_progress(e.id)
        assert p.finished == p.completed == index + 1
    assert p.status == "FINISHED" and p.next_step is None
    first = p.observations[0]
    assert first.step.setting == "opaque-setting" and first.step.duration_s == 9.5
    assert first.deviations == ("setting", "duration_s")
    assert first.shot.grinding.deviation_note == "operator override"
    assert first.shot.grinding.output_g == 18.2
    assert first.shot.brewing.yield_g == 37
    assert e.created_at <= first.shot.plan_frozen_at <= first.shot.grinding_recorded_at
    assert first.shot.grinding_recorded_at <= first.shot.brewing_recorded_at
    assert p.observations[1].deviations == ()
    with pytest.raises(ValueError):
        app.freeze_experiment_step(e.id, e.steps[-1].id)


def test_normal_intent_and_unstarted_design_do_not_change_continuity(repo):
    shot = Acquisition(repo).freeze("s", "opaque-setting", 1, "manual", 9.5)
    finish(repo, shot)
    assert repo.shots("s")[0].intent == ShotIntent.ASSISTED
    e = design()
    repo.add_experiment(e)
    before = Acquisition(repo).preview("s", "opaque-setting")
    assert len(before.plans) == 2
    repo.stop_experiment(e.id, "not needed")
    after = Acquisition(repo).preview("s", "opaque-setting")
    assert [p.model.observation_ids for p in before.plans] == [
        p.model.observation_ids for p in after.plans
    ]
    assert len(repo.shots("s")) == 1


@pytest.mark.parametrize(
    "status,physical,confirmed,eligible",
    [
        (ShotStatus.ABANDONED, False, True, True),
        (ShotStatus.ABANDONED, False, None, False),
        (ShotStatus.INVALIDATED, False, None, False),
        (ShotStatus.ABANDONED, True, None, True),
        (ShotStatus.INVALIDATED, True, None, False),
    ],
)
def test_resolution_progress_and_v3_continuity(repo, status, physical, confirmed, eligible):
    app = Acquisition(repo)
    first = app.freeze("s", "opaque-setting", 1, "manual", 9.5)
    finish(repo, first)
    e = design()
    repo.add_experiment(e)
    shot = app.freeze_experiment_step(e.id, e.steps[0].id)
    if physical:
        grind(repo, shot)
    repo.resolve(shot.id, status, "explicit resolution", no_physical_grinding_confirmed=confirmed)
    p = Repository(repo.path).experiment_progress(e.id)
    assert p.finished == 1 and p.completed == 0 and p.status == "IN_PROGRESS"
    assert p.next_step == e.steps[1]
    assert p.observations[0].shot.resolution.status == status
    assert bool(app.preview("s", "opaque-setting").plans) == eligible
    if confirmed:
        assert all(
            p.model.observation_ids == (first.id,) for p in app.preview("s", "opaque-setting").plans
        )
    app.freeze_experiment_step(e.id, e.steps[1].id)
    assert len(repo.shots("s")) == 3


def test_order_duplicate_pending_cross_session_and_mismatched_plan_rejected(repo):
    e = design()
    repo.add_experiment(e)
    app = Acquisition(repo)
    with pytest.raises(ValueError):
        app.freeze_experiment_step(e.id, e.steps[1].id)
    for step_id, setting, duration in (
        (e.steps[1].id, "opaque-setting", 9.5),
        (e.steps[0].id, "wrong", 9.5),
        (e.steps[0].id, "opaque-setting", 10),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            app.freeze("s", setting, 1, "manual", duration, experiment_step_id=step_id)
    assert not repo.plans("s", 1)
    repo.add_session(Session(id="other", bean_id="b", bean_name="Coffee", started_at=utc_now()))
    with pytest.raises(sqlite3.IntegrityError):
        app.freeze("other", "opaque-setting", 1, "manual", 9.5, experiment_step_id=e.steps[0].id)
    shot = app.freeze_experiment_step(e.id, e.steps[0].id)
    with pytest.raises(ValueError):
        app.freeze("s", "opaque-setting", 2, "manual", 9.5)
    with pytest.raises(sqlite3.IntegrityError):
        repo.stop_experiment(e.id, "pending")
    finish(repo, shot)
    with pytest.raises(sqlite3.IntegrityError):
        app.freeze("s", "opaque-setting", 2, "manual", 9.5, experiment_step_id=e.steps[0].id)
    assert not repo.plans("s", 2)


def test_stop_is_auditable_and_does_not_create_shots(repo):
    e = design()
    repo.add_experiment(e)
    with pytest.raises(ValueError):
        repo.stop_experiment(e.id, " ")
    repo.stop_experiment(e.id, "coffee budget changed")
    p = Repository(repo.path).experiment_progress(e.id)
    assert p.status == "STOPPED" and p.stop_reason == "coffee budget changed"
    assert p.stopped_at >= e.created_at and p.next_step is None
    assert not repo.shots("s")
    with pytest.raises(ValueError):
        Acquisition(repo).freeze_experiment_step(e.id, e.steps[0].id)
    with pytest.raises(sqlite3.IntegrityError):
        Acquisition(repo).freeze(
            "s", "opaque-setting", 1, "manual", 9.5, experiment_step_id=e.steps[0].id
        )
    with pytest.raises(sqlite3.IntegrityError):
        repo.stop_experiment(e.id, "second stop")


def test_design_and_membership_immutable_in_storage(repo):
    e = design()
    repo.add_experiment(e)
    shot = Acquisition(repo).freeze_experiment_step(e.id, e.steps[0].id)
    grind(repo, shot)
    statements = [
        ("UPDATE experiments SET question='revised' WHERE id=?", e.id),
        ("DELETE FROM experiments WHERE id=?", e.id),
        ("UPDATE experiment_steps SET duration_s=1 WHERE id=?", e.steps[0].id),
        ("DELETE FROM experiment_steps WHERE id=?", e.steps[1].id),
        ("UPDATE shots SET experiment_step_id=NULL WHERE id=?", shot.id),
        ("UPDATE shots SET intent='ASSISTED' WHERE id=?", shot.id),
        ("UPDATE shots SET deviation_note='revised' WHERE id=?", shot.id),
        ("INSERT INTO experiment_steps VALUES ('late',?,4,'label',1,'new',1,'extra',NULL)", e.id),
    ]
    with closing(sqlite3.connect(repo.path)) as db, db:
        db.execute("PRAGMA foreign_keys=ON")
        for sql, key in statements:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql, (key,))
    repo.resolve(shot.id, ShotStatus.ABANDONED, "brew abandoned")
    repo.stop_experiment(e.id, "stop")
    with closing(sqlite3.connect(repo.path)) as db, db:
        for sql in ("UPDATE experiment_stops SET reason='revised'", "DELETE FROM experiment_stops"):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
    assert repo.experiments("s") == [e]


def test_invalid_creation_is_atomic(repo):
    e = design()
    with pytest.raises(ValueError):
        repo.add_experiment(replace(e, created_at=utc_now() + timedelta(days=1)))
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_experiment(replace(e, created_at=repo.session("s").started_at - timedelta(days=1)))
    repo.end_session("s")
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_experiment(e)
    assert not repo.experiments("s")
    with closing(sqlite3.connect(repo.path)) as db:
        assert db.execute("SELECT count(*) FROM experiment_steps").fetchone() == (0,)
    with pytest.raises(ValueError):
        repo.experiment_progress("missing")


@pytest.fixture
def v3_path(tmp_path):
    path = tmp_path / "v3.sqlite3"
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript((Path(__file__).parent / "fixtures/schema_v3.sql").read_text())
        db.execute(
            "INSERT INTO sessions VALUES "
            "('s','b','Coffee','2026-09-01T08:00:00+00:00',NULL,'Grinder','Machine',"
            "NULL,NULL,18,36,30,35,NULL)"
        )
        db.execute(
            "INSERT INTO recommendations VALUES "
            "('r','s',1,'2026-09-01T08:01:00+00:00','3E',9.5,18,'manual','1',"
            "NULL,NULL,NULL,1)"
        )
        db.execute(
            "INSERT INTO shots (id, session_id, sequence, created_at, "
            "selected_recommendation_id) VALUES "
            "('shot','s',1,'2026-09-01T08:01:00+00:00','r')"
        )
        db.execute(
            "INSERT INTO shot_resolutions VALUES "
            "('shot','ABANDONED','2026-09-01T08:02:00+00:00','confirmed unground',1)"
        )
        # Retain both fully measured and pending v3 evidence in a second session.
        db.execute(
            "INSERT INTO sessions SELECT 'other', bean_id, bean_name, started_at, "
            "ended_at, grinder, machine, roaster, roast_date, target_puck_dose_g, "
            "target_yield_g, target_time_min_s, target_time_max_s, bag_opened_date "
            "FROM sessions WHERE id='s'"
        )
        for sequence in (1, 2):
            db.execute(
                "INSERT INTO recommendations VALUES "
                "(?, 'other', ?, '2026-09-01T09:00:00+00:00', '3E',9.5,18,"
                "'manual','1',NULL,NULL,NULL,1)",
                (f"other-r{sequence}", sequence),
            )
            db.execute(
                "INSERT INTO shots (id, session_id, sequence, created_at, "
                "selected_recommendation_id) VALUES "
                "(?, 'other', ?, '2026-09-01T09:00:00+00:00', ?)",
                (f"other-shot{sequence}", sequence, f"other-r{sequence}"),
            )
            if sequence == 1:
                db.execute(
                    "UPDATE shots SET actual_setting='3E', actual_duration_s=9.5, "
                    "grinder_output_g=18.2, correction='MEASURED', puck_dose_g=18.05, "
                    "grinding_recorded_at='2026-09-01T09:01:00+00:00', "
                    "brew_duration_s=32, final_yield_g=36.5, notes='retained', "
                    "completed_at='2026-09-01T09:03:00+00:00' WHERE id='other-shot1'"
                )
    return path


def test_v3_migration_preserves_existing_evidence_and_unknown_intent(v3_path):
    with closing(sqlite3.connect(v3_path)) as db:
        before = {
            table: db.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("sessions", "recommendations", "shot_resolutions", "shots")
        }
    repo = Repository(v3_path)
    shot = repo.shots("s")[0]
    assert shot.intent is None and shot.experiment_step_id is None
    assert shot.resolution.no_physical_grinding_confirmed is True
    with closing(sqlite3.connect(v3_path)) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (4,)
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        for table, rows in before.items():
            after = db.execute(f"SELECT * FROM {table}").fetchall()
            assert [row[: len(rows[0])] for row in after] == rows
    assert not repo.experiments("s")
    complete, pending = repo.shots("other")
    assert complete.grinding.puck_dose_g == 18.05 and complete.brewing.yield_g == 36.5
    assert pending.status == ShotStatus.PENDING_GRINDING
    assert complete.intent is pending.intent is None
    assert Repository(v3_path).shots("s") == [shot]
    repo.add_experiment(design())
    new = Acquisition(repo).freeze_experiment_step(
        repo.experiments("s")[0].id, repo.experiments("s")[0].steps[0].id
    )
    assert new.intent == ShotIntent.EXPERIMENT


def test_v3_migration_failure_rolls_back(v3_path, monkeypatch):
    original = schema._execute_schema

    def fail(db, script):
        original(db, script)
        raise sqlite3.OperationalError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(schema, "_execute_schema", fail)
        with pytest.raises(sqlite3.OperationalError):
            Repository(v3_path)
    with closing(sqlite3.connect(v3_path)) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (3,)
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='experiments'").fetchall()
        assert "intent" not in [r[1] for r in db.execute("PRAGMA table_info(shots)")]
    Repository(v3_path)


def test_step_plan_cannot_predate_experiment_or_relabel_completed_shot(repo):
    from espresso_dialin.domain import Plan

    e = design()
    repo.add_experiment(e)
    early = Plan(
        id="early",
        session_id="s",
        target_sequence=1,
        created_at=e.created_at - timedelta(seconds=1),
        setting="opaque-setting",
        duration_s=9.5,
        target_output_g=18,
        selected=True,
    )
    with pytest.raises(sqlite3.IntegrityError):
        repo.freeze("s", 1, [early], experiment_step_id=e.steps[0].id)
    assert not repo.plans("s", 1)
    shot = Acquisition(repo).freeze("s", "opaque-setting", 1, "manual", 9.5)
    finish(repo, shot)
    with pytest.raises(ValueError):
        replace(shot, intent=ShotIntent.EXPERIMENT)
    with closing(sqlite3.connect(repo.path)) as db, db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE shots SET intent='EXPERIMENT', experiment_step_id=? WHERE id=?",
            (e.steps[0].id, shot.id),
        )


def test_finished_attempt_counts_follow_later_invalidation(repo):
    e = design()
    repo.add_experiment(e)
    for step in e.steps:
        shot = Acquisition(repo).freeze_experiment_step(e.id, step.id)
        finish(repo, shot)
    assert repo.experiment_progress(e.id).completed == 3
    repo.resolve(shot.id, ShotStatus.INVALIDATED, "measurement later found wrong")
    p = repo.experiment_progress(e.id)
    assert p.status == "FINISHED" and p.finished == 3 and p.completed == 2
    assert p.observations[-1].shot.grinding.output_g == 18.2
    assert p.observations[-1].shot.brewing.yield_g == 36.5


def test_incomplete_schedule_cannot_be_committed(repo):
    with closing(sqlite3.connect(repo.path)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError), db:
            db.execute(
                "INSERT INTO experiment_steps VALUES "
                "('orphan','missing',1,'opaque',9.5,'ref',1,'reference',NULL)"
            )
        with pytest.raises(sqlite3.IntegrityError), db:
            db.execute(
                "INSERT INTO experiments VALUES "
                "('empty','s',?,'family','question','stop','controls',18,1)",
                (utc_now().isoformat(),),
            )
    assert not repo.experiments("s")
