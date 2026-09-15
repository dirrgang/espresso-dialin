import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from espresso_dialin.application import Acquisition
from espresso_dialin.domain import (
    BrewingResult,
    CorrectionMode,
    GrindingResult,
    Plan,
    Session,
    utc_now,
)
from espresso_dialin.dose_control import score_recommendation
from espresso_dialin.repository import Repository


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "nested" / "live.sqlite3")
    repository.add_session(
        Session(
            id="session",
            bean_id="bean",
            bean_name="Coffee",
            started_at=utc_now(),
            roaster="Roaster",
            roast_date=date(2026, 9, 1),
        )
    )
    return repository


def grind(**kwargs):
    return GrindingResult(
        **(
            {
                "setting": "3E",
                "duration_s": 10.0,
                "output_g": 20.0,
                "correction": CorrectionMode.TO_TARGET,
            }
            | kwargs
        )
    )


def complete_shot(repo, setting="3E", output=20):
    app = Acquisition(repo)
    sequence = len(repo.shots("session")) + 1
    shot = app.freeze("session", setting, sequence, "manual", 9.74)
    repo.save_grinding(shot.id, grind(setting=setting, duration_s=9.70, output_g=output))
    repo.complete(
        shot.id,
        BrewingResult(
            duration_s=32,
            yield_g=36.8,
            purged_before_shot=True,
            obviously_bad_shot=True,
            notes="Uneven flow; retained.",
        ),
    )
    return repo.shots("session")[-1]


def test_empty_path_schema_idempotence_and_restart(repo):
    session = repo.session("session")
    shot = complete_shot(repo)
    plans = repo.plans("session", 1)
    restarted = Repository(repo.path)
    assert restarted.session("session") == session
    assert restarted.shots("session") == [shot]
    assert restarted.plans("session", 1) == plans
    assert shot.grinding.duration_s == 9.70
    assert plans[0].duration_s == 9.74
    assert shot.brewing.notes == "Uneven flow; retained."
    assert shot.brewing.purged_before_shot and shot.brewing.obviously_bad_shot
    assert shot.created_at.utcoffset().total_seconds() == 0
    with closing(sqlite3.connect(repo.path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2


def test_unknown_schema_is_not_overwritten(tmp_path):
    path = tmp_path / "future.sqlite3"
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="unsupported"):
        Repository(path)


def test_manual_fallback_and_incomplete_lifecycle(repo):
    app = Acquisition(repo)
    assert not app.preview("session", "3E").plans
    with pytest.raises(ValueError, match="explicit duration"):
        app.freeze("session", "3E", 1, "manual")
    shot = app.freeze("session", "3E", 1, "manual", 9.74)
    plans = repo.plans("session", 1)
    assert plans[0].model is None and plans[0].strategy_id == "manual"
    assert shot.grinding is None and shot.brewing is None and shot.completed_at is None
    with pytest.raises(ValueError, match="grinding results"):
        repo.complete(shot.id, BrewingResult(duration_s=32, yield_g=36))
    with pytest.raises(ValueError, match="pending"):
        app.preview("session", "3E")
    with pytest.raises(ValueError, match="pending"):
        repo.end_session("session")
    repo.save_grinding(shot.id, grind())
    restarted = Repository(repo.path)
    assert restarted.shots("session")[0].grinding == grind()
    assert restarted.shots("session")[0].completed_at is None
    with pytest.raises(ValueError, match="already saved"):
        repo.save_grinding(shot.id, grind(output_g=99))
    restarted.complete(shot.id, BrewingResult(duration_s=32, yield_g=36))
    assert restarted.plans("session", 1) == plans
    with pytest.raises(ValueError, match="already be completed"):
        restarted.complete(shot.id, BrewingResult(duration_s=31, yield_g=35))


def test_both_shadows_are_frozen_and_score_actual_action(repo):
    first = complete_shot(repo, output=19.4)
    second = complete_shot(repo, output=29.1)
    app = Acquisition(repo)
    preview = app.preview("session", "3E")
    assert len(preview.plans) == 2
    assert {p.model.observation_ids for p in preview.plans} == {(second.id,), (first.id, second.id)}
    shot = app.freeze("session", "3E", 3, "last-shot-proportional")
    frozen = repo.plans("session", 3)
    assert sum(p.selected for p in frozen) == 1
    assert next(p for p in frozen if p.selected).id == shot.selected_recommendation_id
    assert len({p.duration_s for p in frozen}) == 2
    repo.save_grinding(shot.id, grind(duration_s=9.6, output_g=22))
    repo.complete(shot.id, BrewingResult(duration_s=30, yield_g=35))
    assert repo.plans("session", 3) == frozen
    for plan in frozen:
        score = score_recommendation(plan.model, actual_duration_s=9.6, actual_output_g=22)
        assert score.predicted_output_g == plan.model.estimated_rate_g_s * 9.6
        assert score.predicted_output_g != plan.model.expected_output_g


def test_history_is_prior_completed_same_session_and_contiguous_setting(repo):
    complete_shot(repo)
    app = Acquisition(repo)
    assert app.preview("session", "3E").plans
    assert not app.preview("session", "3F").plans
    repo.add_session(Session(id="other", bean_id="bean", bean_name="Coffee", started_at=utc_now()))
    assert not app.preview("other", "3E").plans
    complete_shot(repo, setting="3F")
    assert not app.preview("session", "3E").plans  # returning does not bridge a change
    shot = app.freeze("session", "3E", 3, "manual", 10)
    repo.save_grinding(shot.id, grind(setting="3F"))  # actual setting differs from plan
    repo.complete(shot.id, BrewingResult(duration_s=32, yield_g=36))
    assert not app.preview("session", "3E").plans
    assert app.preview("session", "3F").plans


def test_selection_linkage_and_stale_sequence_rejected_atomically(repo):
    app = Acquisition(repo)
    complete_shot(repo)
    plans = app.preview("session", "3E").plans
    with pytest.raises(ValueError, match="exactly one"):
        repo.freeze("session", 2, plans)
    with pytest.raises(ValueError, match="exactly one"):
        repo.freeze("session", 2, [replace(p, selected=True) for p in plans])
    selected = [replace(p, selected=i == 0) for i, p in enumerate(plans)]
    with pytest.raises(ValueError, match="wrong session/shot"):
        repo.freeze("other", 2, selected)
    with pytest.raises(ValueError, match="wrong session/shot"):
        repo.freeze("session", 3, selected)
    with pytest.raises(ValueError, match="stale preview"):
        app.freeze("session", "3E", 1, "manual", 10)
    with pytest.raises(ValueError, match="exactly one"):
        app.freeze("session", "3E", 2, "invented-strategy")
    assert not repo.plans("session", 2)
    repo.freeze("session", 2, selected)
    with pytest.raises(ValueError, match="pending"):
        repo.freeze("session", 2, selected)


def test_database_guards_frozen_evidence(repo):
    shot = complete_shot(repo)
    with closing(sqlite3.connect(repo.path)) as db:
        for statement in (
            "UPDATE recommendations SET duration_s=999",
            "DELETE FROM recommendations",
            "UPDATE shots SET actual_duration_s=999",
            "UPDATE shots SET selected_recommendation_id='wrong'",
            "DELETE FROM shots",
            "UPDATE sessions SET target_puck_dose_g=99",
            "INSERT INTO recommendations SELECT 'late', session_id, target_sequence, created_at, "
            "setting, duration_s, target_output_g, 'late', model_version, estimated_rate_g_s, "
            "expected_output_g, model_json, 0 FROM recommendations",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(statement)
    assert repo.shots("session")[0] == shot


@pytest.mark.parametrize("mode", list(CorrectionMode))
def test_correction_modes_round_trip(repo, mode):
    shot = Acquisition(repo).freeze("session", "3E", 1, "manual", 10)
    measured = 18.07 if mode == CorrectionMode.MEASURED else None
    repo.save_grinding(shot.id, grind(correction=mode, puck_dose_g=measured))
    result = repo.shots("session")[0].grinding
    assert result.output_g == 20
    assert result.puck_dose_g == measured
    assert result.correction == mode


@pytest.mark.parametrize(
    "mode,mass",
    [
        (CorrectionMode.MEASURED, None),
        (CorrectionMode.NONE, 18),
        (CorrectionMode.TO_TARGET, 18),
        ("INVALID", None),
    ],
)
def test_invalid_correction_modes(mode, mass):
    with pytest.raises(ValueError):
        grind(correction=mode, puck_dose_g=mass)


@pytest.mark.parametrize("number", [0, -1, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("field", ["duration_s", "output_g", "puck_dose_g"])
def test_invalid_grinding_measurements(field, number):
    with pytest.raises(ValueError, match="positive and finite"):
        grind(**{"correction": CorrectionMode.MEASURED, "puck_dose_g": 18, field: number})


@pytest.mark.parametrize("number", [0, -1, float("nan"), float("inf")])
def test_invalid_brewing_session_and_manual_measurements(repo, number):
    for fields in ({"duration_s": number, "yield_g": 36}, {"duration_s": 32, "yield_g": number}):
        with pytest.raises(ValueError):
            BrewingResult(**fields)
    with pytest.raises(ValueError):
        replace(repo.session("session"), target_puck_dose_g=number)
    with pytest.raises(ValueError):
        Acquisition(repo).freeze("session", "3E", 1, "manual", number)
    assert not repo.shots("session")


def test_session_validation_end_and_unknown_id(repo):
    for changes in (
        {"bean_name": " "},
        {"started_at": datetime(2026, 9, 1)},
        {"target_time_max_s": 29},
        {"ended_at": datetime(2020, 1, 1, tzinfo=UTC)},
    ):
        with pytest.raises(ValueError):
            replace(repo.session("session"), **changes)
    with pytest.raises(ValueError, match="unknown session"):
        repo.session("unknown")
    repo.end_session("session")
    assert repo.session("session").ended_at is not None
    with pytest.raises(ValueError, match="ended"):
        Acquisition(repo).preview("session", "3E")


def test_plan_rejects_mismatched_model_context(repo):
    complete_shot(repo)
    plan = Acquisition(repo).preview("session", "3E").plans[0]
    with pytest.raises(ValueError, match="model context"):
        replace(plan, session_id="wrong")
    with pytest.raises(ValueError, match="model context"):
        replace(plan, target_sequence=1)
    with pytest.raises(ValueError, match="blank"):
        Plan(
            id="x",
            session_id="session",
            target_sequence=2,
            created_at=utc_now(),
            setting=" ",
            duration_s=10,
            target_output_g=18,
            selected=True,
        )


def test_freeze_rejects_fabricated_sources_and_timestamps(repo):
    complete_shot(repo)
    plan = replace(Acquisition(repo).preview("session", "3E").plans[0], selected=True)
    for model in (
        replace(plan.model, observation_ids=("missing",)),
        replace(plan.model, bean_id="wrong"),
    ):
        with pytest.raises(ValueError):
            repo.freeze("session", 2, [replace(plan, model=model)])
    for created in (utc_now() + timedelta(days=1), repo.session("session").started_at):
        with pytest.raises(ValueError):
            repo.freeze(
                "session",
                2,
                [replace(plan, created_at=created, model=replace(plan.model, created_at=created))],
            )
    assert not repo.plans("session", 2)


def test_database_link_cannot_cross_sessions_or_select_a_shadow(repo):
    complete_shot(repo)
    app = Acquisition(repo)
    shot = app.freeze("session", "3E", 2, "last-shot-proportional")
    shadow = next(p for p in repo.plans("session", 2) if not p.selected)
    repo.add_session(Session(id="other", bean_id="bean", bean_name="Coffee", started_at=utc_now()))
    with closing(sqlite3.connect(repo.path)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for recommendation_id in (shot.selected_recommendation_id, shadow.id):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(
                    "INSERT INTO shots (id, session_id, sequence, created_at, "
                    "selected_recommendation_id) VALUES (?, ?, ?, ?, ?)",
                    ("invalid", "other", 1, utc_now().isoformat(), recommendation_id),
                )
    assert not repo.shots("other")


def test_duplicate_candidate_failure_rolls_back_entire_freeze(repo):
    complete_shot(repo)
    plan = replace(Acquisition(repo).preview("session", "3E").plans[0], selected=True)
    with pytest.raises(sqlite3.IntegrityError):
        repo.freeze("session", 2, [plan, replace(plan, selected=False)])
    assert not repo.plans("session", 2)
    assert len(repo.shots("session")) == 1
