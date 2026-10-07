import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import timedelta

import pytest

from espresso_dialin.application import Acquisition
from espresso_dialin.domain import (
    BrewingResult,
    CorrectionMode,
    GrindingResult,
    Session,
    Shot,
    ShotResolution,
    ShotStatus,
    utc_now,
)
from espresso_dialin.extraction import ExtractionDirection, recommend_extraction
from espresso_dialin.repository import Repository


@pytest.fixture
def session():
    return Session(id="s", bean_id="b", bean_name="Coffee", started_at=utc_now())


def observation(session, duration=31, yield_g=34, bad=False, sequence=1):
    now = session.started_at
    return Shot(
        id=f"source-{sequence}",
        session_id=session.id,
        sequence=sequence,
        created_at=now,
        selected_recommendation_id="dose",
        grinding=GrindingResult(
            setting="opaque", duration_s=10, output_g=18, correction=CorrectionMode.TO_TARGET
        ),
        brewing=BrewingResult(duration_s=duration, yield_g=yield_g, obviously_bad_shot=bad),
        completed_at=now + timedelta(seconds=1),
    )


@pytest.mark.parametrize("yield_g,expected", [(34, 31 * 36 / 34), (39, 31 * 36 / 39)])
def test_normalization(session, yield_g, expected):
    result = recommend_extraction(
        session,
        [observation(session, yield_g=yield_g)],
        2,
        session.started_at + timedelta(seconds=2),
    )
    assert result.linear_target_yield_time_s == pytest.approx(expected)
    assert result.strategy_id == "linear_yield_direction_baseline"
    assert result.model_version == "1"


@pytest.mark.parametrize(
    "duration,direction",
    [
        (29, "FINER"),
        (30, "KEEP"),
        (32, "KEEP"),
        (35, "KEEP"),
        (36, "COARSER"),
    ],
)
def test_inclusive_band(session, duration, direction):
    result = recommend_extraction(
        session, [observation(session, duration, 36)], 2, session.started_at + timedelta(seconds=2)
    )
    assert result.direction == direction


def test_custom_targets_and_bad_suppression(session):
    session = replace(session, target_yield_g=50, target_time_min_s=20, target_time_max_s=25)
    shots = [observation(session, 12, 25)]
    now = session.started_at + timedelta(seconds=2)
    assert recommend_extraction(session, shots, 2, now).direction == "KEEP"
    shots.append(observation(session, 8, 25, True, 2))
    result = recommend_extraction(session, shots, 3, now)
    assert result.direction == ExtractionDirection.NO_UPDATE_BAD_SHOT
    assert result.source_shot_id == "source-2"
    assert result.linear_target_yield_time_s == 16


def test_eligibility(session):
    shot = observation(session)
    now = session.started_at + timedelta(seconds=2)
    assert recommend_extraction(session, [], 1, now) is None
    assert recommend_extraction(session, [shot], 1, now) is None
    assert recommend_extraction(session, [shot], 2, session.started_at) is None
    assert recommend_extraction(session, [replace(shot, session_id="other")], 2, now) is None
    assert (
        recommend_extraction(session, [replace(shot, brewing=None, completed_at=None)], 2, now)
        is None
    )
    invalid = replace(
        shot,
        resolution=ShotResolution(status=ShotStatus.INVALIDATED, recorded_at=now, reason="invalid"),
    )
    assert recommend_extraction(session, [invalid], 2, now) is None
    latest = replace(
        observation(session, sequence=2),
        resolution=ShotResolution(status=ShotStatus.INVALIDATED, recorded_at=now, reason="invalid"),
    )
    assert recommend_extraction(session, [shot, latest], 3, now).source_shot_id == shot.id


def complete(repo, bad=False):
    shot = Acquisition(repo).freeze("s", "manually chosen", len(repo.shots("s")) + 1, "manual", 10)
    repo.save_grinding(
        shot.id,
        GrindingResult(
            setting="actual opaque", duration_s=10, output_g=18, correction=CorrectionMode.TO_TARGET
        ),
    )
    repo.complete(shot.id, BrewingResult(duration_s=26, yield_g=36, obviously_bad_shot=bad))
    return shot


def test_persistence_chronology_and_invalidation(tmp_path, session):
    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(session)
    assert repo.extraction_feedback("s") is None
    first = complete(repo)
    saved = repo.extraction_recommendations("s")[0]
    assert saved.source_shot_id == first.id and saved.target_sequence == 2
    assert repo.extraction_feedback("s") == saved
    next_shot = Acquisition(repo).freeze("s", "arbitrary next label", 2, "manual", 10)
    assert next_shot.extraction_recommendation_id == saved.id
    assert saved.created_at <= next_shot.created_at
    assert next_shot.brewing is None
    with pytest.raises(ValueError, match="pending"):
        repo.extraction_feedback("s")
    repo.resolve(first.id, ShotStatus.INVALIDATED, "source later found invalid")
    assert Repository(repo.path).shots("s")[1].extraction_recommendation_id == saved.id
    assert repo.extraction_recommendations("s") == [saved]
    repo.resolve(
        next_shot.id, ShotStatus.ABANDONED, "no grind", no_physical_grinding_confirmed=True
    )
    assert repo.extraction_feedback("s") is None
    third = Acquisition(repo).freeze("s", "still manual", 3, "manual", 10)
    assert third.extraction_recommendation_id is None


def test_superseded_feedback_retained_and_bad_persisted(tmp_path, session):
    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(session)
    first = complete(repo)
    second = complete(repo, bad=True)
    old = repo.extraction_feedback("s")
    assert old.direction == "NO_UPDATE_BAD_SHOT"
    repo.resolve(second.id, ShotStatus.INVALIDATED, "invalid")
    new = repo.extraction_feedback("s")
    assert new.source_shot_id == first.id and new.id != old.id
    assert old in repo.extraction_recommendations("s")
    assert len(repo.extraction_recommendations("s")) == 3
    next_shot = Acquisition(repo).freeze("s", "manual", 3, "manual", 10)
    assert next_shot.extraction_recommendation_id == new.id


def test_sql_immutability_and_no_late_insert(tmp_path, session):
    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(session)
    complete(repo)
    complete(repo)
    with closing(sqlite3.connect(repo.path)) as db:
        for sql in (
            "UPDATE extraction_recommendations SET direction='KEEP'",
            "DELETE FROM extraction_recommendations",
            "UPDATE shots SET extraction_recommendation_id=NULL WHERE sequence=2",
            "INSERT INTO extraction_recommendations SELECT 'late',session_id,target_sequence,"
            "source_shot_id,history_through_sequence,created_at,target_yield_g,target_time_min_s,"
            "target_time_max_s,linear_target_yield_time_s,direction,strategy_id,model_version "
            "FROM extraction_recommendations WHERE target_sequence=2",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
            db.rollback()


def test_domain_validation(session):
    feedback = recommend_extraction(
        session, [observation(session)], 2, session.started_at + timedelta(seconds=2)
    )
    for changes in (
        {"target_sequence": 1},
        {"target_yield_g": 0},
        {"linear_target_yield_time_s": float("inf")},
        {"target_time_max_s": 1},
        {"created_at": session.started_at.replace(tzinfo=None)},
    ):
        with pytest.raises(ValueError):
            replace(feedback, **changes)


def test_unknown_session(tmp_path):
    repo = Repository(tmp_path / "live.sqlite3")
    with pytest.raises(ValueError, match="unknown session"):
        repo.extraction_feedback("unknown")


def test_targets_isolation_and_stale_feedback_plan(tmp_path, session):
    from espresso_dialin.domain import Plan

    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(
        replace(session, target_yield_g=50, target_time_min_s=20, target_time_max_s=25)
    )
    repo.add_session(replace(session, id="other"))
    source = complete(repo)
    feedback = repo.extraction_feedback("s")
    assert feedback.target_yield_g == 50
    assert feedback.direction == "COARSER"
    assert repo.extraction_feedback("other") is None
    completed_at = repo.shots("s")[0].completed_at
    # A plan timestamp can follow completion yet predate already persisted feedback.
    now = completed_at + (feedback.created_at - completed_at) / 2
    with pytest.raises(ValueError, match="postdates"):
        repo.freeze(
            "s",
            2,
            [
                Plan(
                    id="stale",
                    session_id="s",
                    target_sequence=2,
                    created_at=now,
                    setting="manual",
                    duration_s=10,
                    target_output_g=18,
                    selected=True,
                )
            ],
        )
    assert repo.plans("s", 2) == []  # failed freeze rolls back dose candidates too
    assert repo.shots("s")[0].id == source.id


def test_source_and_link_sql_guards(tmp_path, session):
    repo = Repository(tmp_path / "live.sqlite3")
    repo.add_session(session)
    repo.add_session(replace(session, id="other"))
    source = complete(repo)
    feedback = repo.extraction_feedback("s")
    repo.resolve(source.id, ShotStatus.INVALIDATED, "invalid source")
    with closing(sqlite3.connect(repo.path)) as db:
        with pytest.raises(sqlite3.IntegrityError, match="prior valid completed source"):
            db.execute(
                "INSERT INTO extraction_recommendations SELECT 'invalid',session_id,"
                "3,source_shot_id,history_through_sequence,created_at,target_yield_g,"
                "target_time_min_s,target_time_max_s,linear_target_yield_time_s,direction,"
                "strategy_id,model_version FROM extraction_recommendations"
            )
        db.rollback()
        db.execute(
            "INSERT INTO recommendations VALUES ('manual','s',2,?, 'choice',10,18,"
            "'manual','1',NULL,NULL,NULL,1)",
            (utc_now().isoformat(),),
        )
        with pytest.raises(sqlite3.IntegrityError, match="prospective extraction link"):
            db.execute(
                "INSERT INTO shots (id,session_id,sequence,created_at,selected_recommendation_id,"
                "intent,extraction_recommendation_id) VALUES ('next','s',2,?,'manual',"
                "'ASSISTED',?)",
                (utc_now().isoformat(), feedback.id),
            )
        db.rollback()
