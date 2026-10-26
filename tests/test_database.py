import sqlite3

import pytest

from agent import database as db

INFO = {
    "caller_name": "Neha", "callback_number": None, "intent_type": "admission", "course_interest": "AI",
    "urgency": "Medium", "sentiment": "Positive", "lead_score": 70, "lead_score_reason": "asked about AI",
    "summary": "Interested in AI course", "suggested_reply": "Hi Neha", "tags": ["Admission", "AI"],
}


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_db(p)
    return p


def test_insert_and_fetch(path):
    call_id = db.insert_call("hello", INFO, source="typed", db_path=path)
    call = db.get_call(call_id, db_path=path)
    assert call["caller_name"] == "Neha"
    assert call["tags"] == "Admission, AI"
    assert call["status"] == "New"
    assert call["source"] == "typed"


def test_filters_and_ordering(path):
    db.insert_call("a", {**INFO, "lead_score": 30, "intent_type": "complaint"}, db_path=path)
    db.insert_call("b", {**INFO, "lead_score": 90}, db_path=path)
    db.insert_call("c", {**INFO, "lead_score": 60, "urgency": "High"}, db_path=path)
    assert [c["lead_score"] for c in db.fetch_calls(order="score", db_path=path)] == [90, 60, 30]
    assert len(db.fetch_calls(intents=["complaint"], db_path=path)) == 1
    assert len(db.fetch_calls(urgencies=["High"], db_path=path)) == 1
    assert len(db.fetch_calls(min_score=60, db_path=path)) == 2


def test_search_matches_name_and_transcript(path):
    db.insert_call("I need a callback about Java", {**INFO, "caller_name": "Zara"}, db_path=path)
    assert len(db.fetch_calls(search="zara", db_path=path)) == 1
    assert len(db.fetch_calls(search="java", db_path=path)) == 1
    assert db.fetch_calls(search="nothing here", db_path=path) == []


def test_update_status_and_delete(path):
    call_id = db.insert_call("x", INFO, db_path=path)
    db.update_status(call_id, "Contacted", db_path=path)
    assert db.get_call(call_id, db_path=path)["status"] == "Contacted"
    with pytest.raises(ValueError):
        db.update_status(call_id, "Bogus", db_path=path)
    db.delete_call(call_id, db_path=path)
    assert db.get_call(call_id, db_path=path) is None


def test_stats(path):
    db.insert_call("a", {**INFO, "lead_score": 80}, db_path=path)
    db.insert_call("b", {**INFO, "lead_score": 40, "intent_type": "complaint"}, db_path=path)
    stats = db.get_stats(db_path=path)
    assert stats["total"] == 2 and stats["high_priority"] == 1 and stats["avg_score"] == 60
    assert stats["by_intent"] == {"admission": 1, "complaint": 1}


def test_init_db_upgrades_old_schema(tmp_path):
    p = tmp_path / "old.db"
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE calls (id INTEGER PRIMARY KEY, created_at TEXT, caller_name TEXT, "
                 "callback_number TEXT, intent_type TEXT, course_interest TEXT, urgency TEXT, sentiment TEXT, "
                 "lead_score INTEGER, lead_score_reason TEXT, summary TEXT, suggested_reply TEXT, tags TEXT, "
                 "raw_transcript TEXT)")
    conn.execute("INSERT INTO calls (created_at, caller_name, lead_score) VALUES ('2026-01-01', 'Old', 50)")
    conn.commit()
    conn.close()
    db.init_db(p)
    assert db.fetch_calls(db_path=p)[0]["status"] == "New"
