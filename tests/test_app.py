from datetime import timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from espresso_dialin.domain import Session, utc_now
from espresso_dialin.repository import Repository

APP = Path(__file__).parents[1] / "app.py"


def widget(items, label):
    return next(item for item in items if item.label == label)


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
    return repo, AppTest.from_file(str(APP)).run()


def test_resume_defaults_to_latest_active_session_and_preserves_explicit_choice(session_app):
    repo, app = session_app
    assert app.selectbox(key="current_session").value == "session-2"
    app.selectbox(key="current_session").select("session-0").run()
    app.run()
    assert app.selectbox(key="current_session").value == "session-0"
    repo.end_session("session-2")
    restarted = AppTest.from_file(str(APP)).run()
    assert restarted.selectbox(key="current_session").value == "session-1"
    repo.end_session("session-1")
    repo.end_session("session-0")
    restarted = AppTest.from_file(str(APP)).run()
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
    app = AppTest.from_file(str(APP)).run()
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
    app = AppTest.from_file(str(APP)).run()
    widget(app.selectbox, "Dose correction").select("TO_TARGET").run()
    widget(app.number_input, "Actual grind duration (s)").set_value(9.70)
    widget(app.number_input, "Grinder output (g)").set_value(17.8)
    widget(app.button, "Save grinding result").click().run()
    assert not app.exception and not app.error
    assert all(not form.proto.form.enter_to_submit for form in app.get("form"))
    app = AppTest.from_file(str(APP)).run()
    widget(app.number_input, "Brew duration (s)").set_value(32.0)
    widget(app.number_input, "Final beverage yield (g)").set_value(36.8)
    widget(app.checkbox, "Obviously bad shot").check()
    widget(app.text_area, "Notes (optional)").input("Smoke test")
    widget(app.button, "Complete shot").click().run()
    assert not app.exception and not app.error
    assert repo.plans(session.id, 1) == frozen
    shot = repo.shots(session.id)[0]
    assert shot.grinding.duration_s == 9.7
    assert shot.grinding.puck_dose_g is None
    assert shot.brewing.yield_g == 36.8
    assert shot.brewing.obviously_bad_shot
    app = AppTest.from_file(str(APP)).run()
    widget(app.text_input, "Grinder setting").input("3E").run()
    assert len(app.table[0].value) == 2
    widget(app.selectbox, "Selected strategy").select("past-only-median-rate").run()
    widget(app.button, "Freeze plan before grinding").click().run()
    assert not app.exception and not app.error
    plans = repo.plans(session.id, 2)
    assert len(plans) == 2 and sum(p.selected for p in plans) == 1
    assert all(p.model.observation_ids == (shot.id,) for p in plans)
