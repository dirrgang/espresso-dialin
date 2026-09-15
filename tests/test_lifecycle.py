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


def start(repo, setting="3E", duration_s=9.74):
    return Acquisition(repo).freeze("s", setting, len(repo.shots("s")) + 1, "manual", duration_s)


def grind(repo, shot, setting="3E", duration_s=9.7, output_g=20):
    repo.save_grinding(
        shot.id,
        GrindingResult(
            setting=setting,
            duration_s=duration_s,
            output_g=output_g,
            correction=CorrectionMode.TO_TARGET,
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
    pregrind_abandonment = status == ShotStatus.ABANDONED and not has_grinding
    reason = "Typo"
    if status == ShotStatus.ABANDONED:
        reason = (
            "Brew stopped; grinder result valid"
            if has_grinding
            else "Confirmed no physical grinding occurred"
        )
    repo.resolve(
        shot.id,
        status,
        reason,
        no_physical_grinding_confirmed=True if pregrind_abandonment else None,
    )
    resolved = Repository(repo.path).shots("s")[0]
    assert resolved.status == status and not resolved.pending
    assert replace(resolved, resolution=None) == original
    assert resolved.resolution is not None
    assert resolved.resolution.reason
    assert resolved.resolution.no_physical_grinding_confirmed is (
        True if pregrind_abandonment else None
    )
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
    models = tuple(plan.model for plan in preview.plans if plan.model is not None)
    assert len(models) == len(preview.plans)
    assert all(model.observation_ids == (second.id,) for model in models)
    assert repo.plans("s", 2) == frozen


def test_pregrind_abandonment_is_transparent_to_existing_history(repo):
    first = start(repo)
    grind(repo, first)
    repo.complete(first.id, BrewingResult(duration_s=32, yield_g=36))
    second = start(repo)
    repo.resolve(
        second.id,
        ShotStatus.ABANDONED,
        "Confirmed no physical grinding occurred",
        no_physical_grinding_confirmed=True,
    )
    models = tuple(plan.model for plan in Acquisition(repo).preview("s", "3E").plans if plan.model)
    assert {model.observation_ids for model in models} == {(first.id,)}


def test_unconfirmed_pregrind_abandonment_remains_a_continuity_break(repo):
    first = start(repo)
    grind(repo, first)
    repo.complete(first.id, BrewingResult(duration_s=32, yield_g=36))
    second = start(repo)
    repo.resolve(second.id, ShotStatus.ABANDONED, "No reliable grinding result")
    resolved = repo.shots("s")[1]
    assert resolved.resolution is not None
    assert resolved.resolution.no_physical_grinding_confirmed is None
    assert not Acquisition(repo).preview("s", "3E").plans


def test_multiple_confirmed_pregrind_abandonments_are_transparent(repo):
    first = start(repo)
    grind(repo, first)
    repo.complete(first.id, BrewingResult(duration_s=32, yield_g=36))
    for _ in range(2):
        abandoned = start(repo)
        repo.resolve(
            abandoned.id,
            ShotStatus.ABANDONED,
            "Confirmed no physical grinding occurred",
            no_physical_grinding_confirmed=True,
        )
    assert all(
        plan.model is not None and plan.model.observation_ids == (first.id,)
        for plan in Acquisition(repo).preview("s", "3E").plans
    )


def test_pregrind_invalidation_still_breaks_continuity(repo):
    first = start(repo)
    grind(repo, first)
    repo.complete(first.id, BrewingResult(duration_s=32, yield_g=36))
    second = start(repo)
    repo.resolve(second.id, ShotStatus.INVALIDATED, "Execution is uncertain")
    assert not Acquisition(repo).preview("s", "3E").plans


def test_abandoned_valid_grinding_observation_obeys_actual_setting_continuity(repo):
    first = start(repo)
    grind(repo, first)
    repo.resolve(first.id, ShotStatus.ABANDONED, "Grinding valid; brew abandoned")
    assert Acquisition(repo).preview("s", "3E").plans
    assert not Acquisition(repo).preview("s", "3F").plans

    second = start(repo, "3F")
    grind(repo, second, setting="3F")
    repo.resolve(second.id, ShotStatus.ABANDONED, "Grinding valid; brew abandoned")
    assert Acquisition(repo).preview("s", "3F").plans
    assert not Acquisition(repo).preview("s", "3E").plans


def test_non_execution_confirmation_rejects_physical_evidence_or_invalidation(repo):
    ground = start(repo)
    grind(repo, ground)
    with pytest.raises(ValueError, match="no physical evidence"):
        repo.resolve(
            ground.id,
            ShotStatus.ABANDONED,
            "Impossible confirmation",
            no_physical_grinding_confirmed=True,
        )
    repo.resolve(ground.id, ShotStatus.ABANDONED, "Grinding valid; brew abandoned")

    unknown = start(repo)
    with pytest.raises(ValueError, match="only an abandoned shot"):
        repo.resolve(
            unknown.id,
            ShotStatus.INVALIDATED,
            "Execution uncertain",
            no_physical_grinding_confirmed=True,
        )


def test_real_world_pregrind_gap_preserves_preview_and_frozen_source_ids(repo):
    first = start(repo, "4E", 8.75)
    grind(repo, first, setting="4E", duration_s=8.75, output_g=15.30)
    repo.complete(first.id, BrewingResult(duration_s=30, yield_g=37.37))

    unexecuted = start(repo, "4E", 10.3)
    repo.resolve(
        unexecuted.id,
        ShotStatus.ABANDONED,
        "Wrong selection; confirmed no physical grinding occurred",
        no_physical_grinding_confirmed=True,
    )

    newest = start(repo, "4E", 10.3)
    grind(repo, newest, setting="4E", duration_s=10.3, output_g=19.65)
    repo.complete(newest.id, BrewingResult(duration_s=57, yield_g=35.43))

    preview = Acquisition(repo).preview("s", "4E")
    by_strategy = {plan.strategy_id: plan for plan in preview.plans}
    last = by_strategy["last-shot-proportional"]
    median = by_strategy["past-only-median-rate"]
    assert last.model is not None and last.model.observation_ids == (newest.id,)
    assert median.model is not None and median.model.observation_ids == (first.id, newest.id)
    assert last.duration_s == pytest.approx(9.4351, abs=0.0001)
    assert median.duration_s == pytest.approx(9.8459, abs=0.0001)

    frozen = Acquisition(repo).freeze("s", "4E", 4, "past-only-median-rate")
    assert frozen.sequence == 4
    persisted = {plan.strategy_id: plan.model for plan in repo.plans("s", 4)}
    last_model = persisted["last-shot-proportional"]
    median_model = persisted["past-only-median-rate"]
    assert last_model is not None and last_model.observation_ids == (newest.id,)
    assert median_model is not None and median_model.observation_ids == (first.id, newest.id)


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
