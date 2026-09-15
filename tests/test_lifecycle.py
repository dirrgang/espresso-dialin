import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from espresso_dialin.application import Acquisition
from espresso_dialin.domain import (
    BrewingResult,
    CorrectionMode,
    GrindingResult,
    Session,
    ShotResolution,
    ShotStatus,
    utc_now,
)
from espresso_dialin.repository import Repository


@pytest.fixture
def repo(tmp_path):
    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(
        Session(
            id="s",
            bean_id="b",
            bean_name="Coffee",
            started_at=utc_now(),
            bag_opened_date=date(2026, 9, 1),
        )
    )
    return repo


def start(repo):
    return Acquisition(repo).freeze("s", "3E", len(repo.shots("s")) + 1, "manual", 9.74)


def grind(repo, shot):
    repo.save_grinding(
        shot.id,
        GrindingResult(
            setting="3E", duration_s=9.7, output_g=20, correction=CorrectionMode.TO_TARGET
        ),
    )


def test_recording_timestamps_and_bag_context_survive_restart(repo):
    shot = start(repo)
    assert shot.plan_frozen_at == shot.created_at
    assert shot.grinding_recorded_at is None and shot.brewing_recorded_at is None
    before = utc_now()
    grind(repo, shot)
    ground = repo.shots("s")[0]
    assert before <= ground.grinding_recorded_at <= utc_now()
    assert ground.brewing_recorded_at is None
    before_brew = utc_now()
    repo.complete(shot.id, BrewingResult(duration_s=32, yield_g=36))
    done = repo.shots("s")[0]
    assert before_brew <= done.brewing_recorded_at <= utc_now()
    for time in (done.plan_frozen_at, done.grinding_recorded_at, done.brewing_recorded_at):
        assert time.utcoffset() == timedelta(0)
    restarted = Repository(repo.path)
    assert restarted.shots("s") == [done]
    assert restarted.session("s").bag_opened_date == date(2026, 9, 1)
    assert restarted.session("s").roast_date is None


@pytest.mark.parametrize("status", [ShotStatus.ABANDONED, ShotStatus.INVALIDATED])
@pytest.mark.parametrize("has_grinding", [False, True])
def test_resolutions_retain_evidence_release_session_and_control_eligibility(
    repo, status, has_grinding
):
    shot = start(repo)
    if has_grinding:
        grind(repo, shot)
    original = repo.shots("s")[0]
    frozen = repo.plans("s", 1)
    repo.resolve(
        shot.id, status, "Physical brew stopped" if status == ShotStatus.ABANDONED else "Typo"
    )
    resolved = Repository(repo.path).shots("s")[0]
    assert resolved.status == status and not resolved.pending
    assert replace(resolved, resolution=None) == original
    assert resolved.resolution.reason
    assert repo.plans("s", 1) == frozen
    assert bool(Acquisition(repo).preview("s", "3E").plans) == (
        has_grinding and status == ShotStatus.ABANDONED
    )
    with pytest.raises(ValueError):
        repo.complete(shot.id, BrewingResult(duration_s=32, yield_g=36))
    with pytest.raises(ValueError):
        grind(repo, shot)
    for second_status in (ShotStatus.ABANDONED, ShotStatus.INVALIDATED):
        with pytest.raises(ValueError, match="already"):
            repo.resolve(shot.id, second_status, "Repeated action")
    assert start(repo).sequence == 2


def test_completed_invalidation_keeps_measurement_and_already_frozen_predictions(repo):
    first = start(repo)
    grind(repo, first)
    repo.complete(first.id, BrewingResult(duration_s=32, yield_g=36))
    second = Acquisition(repo).freeze("s", "3E", 2, "past-only-median-rate")
    frozen = repo.plans("s", 2)
    repo.resolve(first.id, ShotStatus.INVALIDATED, "Grind duration was mistyped")
    assert repo.shots("s")[0].grinding.duration_s == 9.7
    assert repo.shots("s")[0].completed_at is not None
    assert repo.plans("s", 2) == frozen
    grind(repo, second)
    repo.complete(second.id, BrewingResult(duration_s=31, yield_g=36))
    preview = Acquisition(repo).preview("s", "3E")
    assert all(plan.model.observation_ids == (second.id,) for plan in preview.plans)
    assert repo.plans("s", 2) == frozen


def test_invalidated_and_unknown_shots_break_continuity(repo):
    first = start(repo)
    grind(repo, first)
    repo.resolve(first.id, ShotStatus.ABANDONED, "Brew abandoned; grinder result valid")
    second = start(repo)
    repo.resolve(second.id, ShotStatus.ABANDONED, "No reliable grinding result")
    assert not Acquisition(repo).preview("s", "3E").plans


def test_reject_stale_prediction_if_source_is_invalidated_before_freeze(repo):
    first = start(repo)
    grind(repo, first)
    repo.complete(first.id, BrewingResult(duration_s=32, yield_g=36))
    plan = replace(Acquisition(repo).preview("s", "3E").plans[0], selected=True)
    repo.resolve(first.id, ShotStatus.INVALIDATED, "Typo discovered in another tab")
    with pytest.raises(ValueError):
        repo.freeze("s", 2, [plan])
    assert not repo.plans("s", 2)


def test_resolution_validation_and_immutable_sql_guards(repo):
    shot = start(repo)
    for reason in ("", "  "):
        with pytest.raises(ValueError, match="reason"):
            repo.resolve(shot.id, ShotStatus.INVALIDATED, reason)
    for status in (ShotStatus.COMPLETED, "INVALIDATED"):
        with pytest.raises(ValueError):
            repo.resolve(shot.id, status, "Invalid action")
    with pytest.raises(ValueError, match="timezone-aware"):
        ShotResolution(
            status=ShotStatus.INVALIDATED, recorded_at=datetime(2026, 9, 1), reason="Typo"
        )
    grind(repo, shot)
    repo.resolve(shot.id, ShotStatus.ABANDONED, "Valid grind; no brew")
    with closing(sqlite3.connect(repo.path)) as db:
        for sql in (
            "UPDATE shots SET actual_duration_s=99",
            "DELETE FROM shots",
            "UPDATE shot_resolutions SET reason='changed'",
            "DELETE FROM shot_resolutions",
            "UPDATE recommendations SET duration_s=99",
            "UPDATE sessions SET bag_opened_date='2026-09-02'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
    repo.end_session("s")
    assert repo.session("s").ended_at is not None


def test_completed_shot_cannot_be_abandoned_and_clock_reversal_rejected(repo, monkeypatch):
    shot = start(repo)
    grind(repo, shot)
    with closing(sqlite3.connect(repo.path)) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE shots SET actual_duration_s=99")
    repo.complete(shot.id, BrewingResult(duration_s=32, yield_g=36))
    with pytest.raises(ValueError, match="pending"):
        repo.resolve(shot.id, ShotStatus.ABANDONED, "Already brewed")
    monkeypatch.setattr(
        "espresso_dialin.repository.utc_now", lambda: shot.created_at - timedelta(days=1)
    )
    with pytest.raises(ValueError, match="precede"):
        repo.resolve(shot.id, ShotStatus.INVALIDATED, "Clock moved backwards")
