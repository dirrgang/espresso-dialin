from datetime import timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from espresso_dialin.domain import Session, ShotStatus, utc_now
from espresso_dialin.repository import Repository

APP = Path(__file__).parents[1] / "streamlit_app.py"
APP_TEST_TIMEOUT_S = 10


def widget(items, label):
    return next(item for item in items if item.label == label)


def start_app():
    return AppTest.from_file(str(APP), default_timeout=APP_TEST_TIMEOUT_S).run()


@pytest.fixture
def session_app(tmp_path, monkeypatch):
    path = tmp_path / "sessions.sqlite3"
    monkeypatch.setenv("ESPRESSO_DIALIN_DB", str(path))
    repo = Repository(path)
    now = utc_now()
    for i in range(3):
        repo.add_session(
            Session(
                id=f"session-{i}",
                bean_id="bean",
                bean_name="Test bean",
                started_at=now - timedelta(days=3 - i),
            )
        )
    return repo, start_app()


def test_resume_defaults_to_latest_active_session_and_preserves_explicit_choice(session_app):
    repo, app = session_app
    assert app.selectbox(key="current_session").value == "session-2"
    app.selectbox(key="current_session").select("session-0").run()
    app.run()
    assert app.selectbox(key="current_session").value == "session-0"
    repo.end_session("session-2")
    restarted = start_app()
    assert restarted.selectbox(key="current_session").value == "session-1"
    repo.end_session("session-1")
    repo.end_session("session-0")
    restarted = start_app()
    assert restarted.selectbox(key="current_session").value == "session-2"
    assert not restarted.exception


def test_invalid_session_form_preserves_selection_and_pending_inputs(session_app):
    repo, app = session_app
    # Choose a session other than either the oldest or the fresh-browser default.
    app.selectbox(key="current_session").select("session-1").run()
    widget(app.text_input, "Grinder setting").input("3E").run()
    widget(app.number_input, "Manual planned duration (s)").set_value(9.74).run()
    widget(app.button, "Create session").click().run()
    assert app.error and not app.exception
    assert app.selectbox(key="current_session").value == "session-1"
    assert widget(app.text_input, "Grinder setting").value == "3E"
    assert widget(app.number_input, "Manual planned duration (s)").value == 9.74
    app.run()
    assert app.selectbox(key="current_session").value == "session-1"
    assert len(repo.sessions()) == 3


def test_invalid_shot_forms_keep_history_and_allow_retry(session_app):
    repo, app = session_app
    widget(app.text_input, "Grinder setting").input("3E").run()
    widget(app.button, "Freeze plan before grinding").click().run()
    assert app.error and not app.exception
    assert any(header.value == "Recent history" for header in app.header)
    assert not repo.shots("session-2")
    widget(app.number_input, "Manual planned duration (s)").set_value(9.74).run()
    widget(app.button, "Freeze plan before grinding").click().run()
    widget(app.number_input, "Actual grind duration (s)").set_value(9.70)
    widget(app.button, "Save grinding result").click().run()
    assert app.error and not app.exception
    assert len(app.dataframe) == 1
    assert widget(app.number_input, "Actual grind duration (s)").value == 9.70
    widget(app.number_input, "Grinder output (g)").set_value(18.0)
    widget(app.button, "Save grinding result").click().run()
    assert not app.error and not app.exception
    widget(app.number_input, "Brew duration (s)").set_value(32.0)
    widget(app.button, "Complete shot").click().run()
    assert app.error and not app.exception
    assert len(app.dataframe) == 1
    assert repo.shots("session-2")[0].completed_at is None
    widget(app.number_input, "Final beverage yield (g)").set_value(36.0)
    widget(app.button, "Complete shot").click().run()
    assert not app.error and not app.exception
    assert repo.shots("session-2")[0].completed_at is not None


def test_live_workflow_and_restart(tmp_path, monkeypatch):
    path = tmp_path / "smoke.sqlite3"
    monkeypatch.setenv("ESPRESSO_DIALIN_DB", str(path))
    app = start_app()
    assert not app.exception
    assert all(not form.proto.form.enter_to_submit for form in app.get("form"))
    widget(app.selectbox, "Bean").select("REWE Bio Espresso ganze Bohnen, 1000 g").run()
    widget(app.button, "Create session").click().run()
    assert not app.exception and not app.error
    widget(app.text_input, "Grinder setting").input("3E").run()
    assert any("Insufficient" in info.value for info in app.info)
    widget(app.number_input, "Manual planned duration (s)").set_value(9.74).run()
    widget(app.button, "Freeze plan before grinding").click().run()
    assert not app.exception and not app.error
    repo = Repository(path)
    session = repo.sessions()[0]
    frozen = repo.plans(session.id, 1)
    assert repo.shots(session.id)[0].grinding is None
    assert all(not form.proto.form.enter_to_submit for form in app.get("form"))
    # Restart between physical phases, so widget state cannot mask persistence errors.
    app = start_app()
    widget(app.selectbox, "Dose correction").select("TO_TARGET").run()
    widget(app.number_input, "Actual grind duration (s)").set_value(9.70)
    widget(app.number_input, "Grinder output (g)").set_value(17.8)
    widget(app.button, "Save grinding result").click().run()
    assert not app.exception and not app.error
    assert all(not form.proto.form.enter_to_submit for form in app.get("form"))
    app = start_app()
    widget(app.number_input, "Brew duration (s)").set_value(32.0)
    widget(app.number_input, "Final beverage yield (g)").set_value(36.8)
    widget(app.checkbox, "Obviously bad shot").check()
    widget(app.text_area, "Notes (optional)").input("Smoke test")
    widget(app.button, "Complete shot").click().run()
    assert not app.exception and not app.error
    assert repo.plans(session.id, 1) == frozen
    shot = repo.shots(session.id)[0]
    assert shot.grinding is not None
    assert shot.grinding.duration_s == 9.7
    assert shot.grinding.puck_dose_g is None
    assert shot.brewing is not None
    assert shot.brewing.yield_g == 36.8
    assert shot.brewing.obviously_bad_shot
    app = start_app()
    widget(app.text_input, "Grinder setting").input("3E").run()
    assert len(app.table[0].value) == 2
    widget(app.selectbox, "Selected strategy").select("past-only-median-rate").run()
    widget(app.button, "Freeze plan before grinding").click().run()
    assert not app.exception and not app.error
    plans = repo.plans(session.id, 2)
    assert len(plans) == 2 and sum(p.selected for p in plans) == 1
    models = tuple(p.model for p in plans if p.model is not None)
    assert len(models) == len(plans)
    assert all(model.observation_ids == (shot.id,) for model in models)


def test_abandon_brew_restart_then_invalidate_and_continue(session_app):
    repo, app = session_app
    widget(app.text_input, "Grinder setting").input("3E").run()
    widget(app.number_input, "Manual planned duration (s)").set_value(9.74).run()
    widget(app.button, "Freeze plan before grinding").click().run()
    widget(app.number_input, "Actual grind duration (s)").set_value(9.7)
    widget(app.number_input, "Grinder output (g)").set_value(18)
    widget(app.button, "Save grinding result").click().run()
    assert not app.exception and not app.error
    widget(app.text_area, "Reason (required)").input("Brew abandoned; grinder result is valid")
    widget(app.button, "Confirm shot resolution").click().run()
    assert app.error  # confirmation is required
    assert repo.shots("session-2")[0].pending
    widget(app.checkbox, "I confirm this action and its effect on controller history").check()
    widget(app.button, "Confirm shot resolution").click().run()
    assert not app.exception and not app.error
    first = repo.shots("session-2")[0]
    assert first.status == ShotStatus.ABANDONED and first.grinding_recorded_at is not None
    app = start_app()
    widget(app.text_input, "Grinder setting").input("3E").run()
    widget(app.selectbox, "Selected strategy").select("past-only-median-rate").run()
    widget(app.button, "Freeze plan before grinding").click().run()
    assert all(p.model.observation_ids == (first.id,) for p in repo.plans("session-2", 2))
    widget(app.selectbox, "Action").select(ShotStatus.INVALIDATED).run()
    widget(app.checkbox, "I confirm this action and its effect on controller history").check()
    widget(app.button, "Confirm shot resolution").click().run()
    assert app.error  # reason is required too
    widget(app.text_area, "Reason (required)").input("Wrong planned setting; did not grind")
    widget(app.button, "Confirm shot resolution").click().run()
    assert not app.exception and not app.error
    assert repo.shots("session-2")[1].status == ShotStatus.INVALIDATED
    app = start_app()
    widget(app.text_input, "Grinder setting").input("3E").run()
    assert any("Insufficient" in info.value for info in app.info)
    widget(app.number_input, "Manual planned duration (s)").set_value(9.7).run()
    widget(app.button, "Freeze plan before grinding").click().run()
    assert not app.exception and not app.error
    assert repo.shots("session-2")[-1].sequence == 3


def test_completed_shot_can_be_invalidated_through_ui(session_app):
    repo, app = session_app
    from espresso_dialin.application import Acquisition
    from espresso_dialin.domain import BrewingResult, CorrectionMode, GrindingResult

    shot = Acquisition(repo).freeze("session-2", "3E", 1, "manual", 9.74)
    repo.save_grinding(
        shot.id,
        GrindingResult(setting="3E", duration_s=97, output_g=18, correction=CorrectionMode.NONE),
    )
    repo.complete(shot.id, BrewingResult(duration_s=32, yield_g=36))
    app.run()
    widget(app.text_area, "Reason (required)").input("97 seconds was a typo for 9.7")
    widget(app.checkbox, "I confirm this action and its effect on controller history").check()
    widget(app.button, "Confirm shot resolution").click().run()
    assert not app.exception and not app.error
    invalid = repo.shots("session-2")[0]
    assert invalid.status == ShotStatus.INVALIDATED
    assert invalid.grinding.duration_s == 97
