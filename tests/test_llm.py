import pytest

from agent import llm
from agent.llm import AgentError
from tests.fakes import FakeClient, good_reply


def test_parse_json_tolerant_handles_fences_and_extra_text():
    raw = 'Sure! Here you go:\n```json\n{"a": 1}\n```\nHope that helps.'
    assert llm.parse_json_tolerant(raw) == {"a": 1}


def test_parse_json_basic_fails_on_extra_text():
    with pytest.raises(ValueError):
        llm.parse_json_basic('Here it is: {"a": 1}')


def test_check_schema_flags_bad_values():
    parsed = {k: None for k in llm.REQUIRED_KEYS}
    parsed.update(intent_type="Admission", urgency="High", sentiment="Positive", lead_score=50, tags=[])
    problems = llm.check_schema(parsed)
    assert any("intent_type" in p for p in problems)


def test_check_schema_accepts_good_reply():
    import json
    assert llm.check_schema(json.loads(good_reply())) == []


def test_normalize_repairs_values():
    record = llm.normalize({
        "intent_type": "Fee Inquiry", "urgency": "high", "sentiment": "angry", "lead_score": "140",
        "tags": "#Fees, #Python", "caller_name": "null", "callback_number": "",
    })
    assert record["intent_type"] == "fee_inquiry"
    assert record["urgency"] == "High"
    assert record["sentiment"] == "Neutral"
    assert record["lead_score"] == 100
    assert record["tags"] == ["Fees", "Python"]
    assert record["caller_name"] is None and record["callback_number"] is None


def test_v2_retries_after_bad_json_and_records_first_attempt_failure():
    client = FakeClient(replies=["not json at all", good_reply()])
    result = llm.extract_lead_detailed(client, "I want to join", "v2")
    assert result.record is not None
    assert result.attempts == 2
    assert result.first_json_ok is False


def test_v1_does_not_retry():
    client = FakeClient(replies=["not json at all", good_reply()])
    result = llm.extract_lead_detailed(client, "I want to join", "v1")
    assert result.record is None
    assert result.attempts == 1
    assert result.error_type == "invalid_json"


def test_api_error_is_captured_not_raised():
    client = FakeClient(replies=[TimeoutError("timed out")])
    result = llm.extract_lead_detailed(client, "hello", "v2")
    assert result.record is None
    assert result.error_type == "api_error"
    assert "TimeoutError" in result.error


def test_v2_uses_json_mode_and_v1_does_not():
    client = FakeClient(replies=[good_reply()])
    llm.extract_lead_detailed(client, "hello", "v2")
    assert client.last_kwargs["response_format"] == {"type": "json_object"}
    client = FakeClient(replies=[good_reply()])
    llm.extract_lead_detailed(client, "hello", "v1")
    assert "response_format" not in client.last_kwargs


def test_json_mode_rejection_falls_back_to_plain_request():
    client = FakeClient(replies=[Exception("json_validate_failed"), good_reply()])
    result = llm.extract_lead_detailed(client, "hello", "v2")
    assert result.record is not None


def test_extract_lead_raises_agent_error_on_empty_transcript():
    with pytest.raises(AgentError):
        llm.extract_lead(FakeClient(), "   ")


def test_transcribe_rejects_empty_result():
    with pytest.raises(AgentError):
        llm.transcribe(FakeClient(transcript_text="  "), b"data", "x.wav")
