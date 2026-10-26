"""Drive the real Streamlit app with Streamlit's test runner. No network and no API key needed."""

import pytest
from streamlit.testing.v1 import AppTest

from agent import config, database as db
from tests.fakes import FakeClient, good_reply


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "app.db")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    return AppTest.from_file(str(config.BASE_DIR / "app.py"), default_timeout=30)


def goto(at: AppTest, page: str) -> AppTest:
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception
    return at


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def test_empty_dashboard_offers_demo_data(app):
    app.run()
    assert not app.exception
    assert any("No calls yet" in i.value for i in app.info)


def test_every_page_renders_with_demo_data(app):
    app.run()
    button(app, "Load demo leads").click().run()
    assert not app.exception
    assert app.metric[0].value == "8"
    for page in ["Dashboard", "New call", "Leads", "Evaluation", "Settings"]:
        goto(app, page)


def test_analysing_without_a_key_shows_a_clear_error(app):
    app.run()
    goto(app, "New call")
    next(t for t in app.text_area if t.label == "Call transcript").set_value("I want to join").run()
    button(app, "Analyse transcript").click().run()
    assert any("Groq API key" in e.value for e in app.error)


def test_analyse_and_save_flow(app, monkeypatch):
    import agent.llm as llm
    fake = FakeClient(responder=lambda transcript, n: good_reply(caller_name="Rahul"))
    monkeypatch.setattr(llm, "get_client", lambda key=None: fake)

    app.run()
    app.sidebar.text_input[0].set_value("test-key")
    goto(app, "New call")
    next(t for t in app.text_area if t.label == "Call transcript").set_value("Hi I'm Rahul, I want to join AI").run()
    button(app, "Analyse transcript").click().run()
    assert not app.exception, app.exception
    assert any(m.label == "Lead score" and m.value == "90/100" for m in app.metric)

    button(app, "Save lead").click().run()
    assert not app.exception, app.exception
    calls = db.fetch_calls()
    assert len(calls) == 1 and calls[0]["caller_name"] == "Rahul" and calls[0]["source"] == "typed"
    assert any("Saved lead" in s.value for s in app.success)
