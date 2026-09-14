from pathlib import Path

from streamlit.testing.v1 import AppTest

from espresso_dialin.repository import Repository

APP = Path(__file__).parents[1] / "app.py"


def widget(items, label):
    return next(item for item in items if item.label == label)


def test_live_workflow_and_restart(tmp_path, monkeypatch):
    path = tmp_path / "smoke.sqlite3"
    monkeypatch.setenv("ESPRESSO_DIALIN_DB", str(path))
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
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
    # Restart between physical phases, so widget state cannot mask persistence errors.
    app = AppTest.from_file(str(APP)).run()
    widget(app.selectbox, "Dose correction").select("TO_TARGET").run()
    widget(app.number_input, "Actual grind duration (s)").set_value(9.70)
    widget(app.number_input, "Grinder output (g)").set_value(17.8)
    widget(app.button, "Save grinding result").click().run()
    assert not app.exception and not app.error
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
