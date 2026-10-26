"""Fake Groq client for tests, so no network or API key is needed."""

import json
from types import SimpleNamespace


def _chat_response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeClient:
    """Returns scripted chat replies in order, or calls `responder(transcript, call_no)`."""

    def __init__(self, replies=None, responder=None, transcript_text="hello"):
        self.replies = list(replies or [])
        self.responder = responder
        self.calls = 0
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=lambda **kw: SimpleNamespace(text=transcript_text)))

    def _create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self.responder:
            return _chat_response(self.responder(kwargs["messages"][-1]["content"], self.calls))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return _chat_response(reply)


def good_reply(**overrides) -> str:
    record = {
        "caller_name": "Rahul", "callback_number": "9876501234", "intent_type": "admission",
        "course_interest": "AI", "urgency": "High", "sentiment": "Positive", "lead_score": 90,
        "lead_score_reason": "wants to join today", "summary": "Wants to join the AI course.",
        "suggested_reply": "Thanks Rahul, we will call you today.", "tags": ["Admission", "AI"],
    }
    record.update(overrides)
    return json.dumps(record)
