"""Groq calls for speech-to-text and lead extraction, plus output validation."""

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from groq import Groq

from . import config
from .prompts import DEFAULT_PROMPT, PROMPTS


class AgentError(Exception):
    """Raised for problems the user can act on (missing key, bad audio, API failure)."""


REQUIRED_KEYS = [
    "caller_name", "callback_number", "intent_type", "course_interest", "urgency",
    "sentiment", "lead_score", "lead_score_reason", "summary", "suggested_reply", "tags",
]


# ---------------------------------------------------------------- model selection
_working: dict = {}  # model that last worked, per kind ("chat" or "speech")


def _model_missing(exc: Exception) -> bool:
    text = str(exc).lower()
    return "model_not_found" in text or ("model" in text and "does not exist" in text)


def _candidates(kind: str) -> list:
    configured, fallbacks = (
        (config.CHAT_MODEL, config.CHAT_FALLBACKS) if kind == "chat"
        else (config.WHISPER_MODEL, config.SPEECH_FALLBACKS)
    )
    order = [_working[kind]] if kind in _working else [configured, *fallbacks]
    return list(dict.fromkeys(order))


def _with_model_fallback(kind: str, call):
    """Run call(model), moving to the next model if Groq reports the model no longer exists."""
    tried, last = [], None
    for model in _candidates(kind):
        try:
            result = call(model)
        except Exception as exc:
            if _model_missing(exc):
                tried.append(model)
                last = exc
                continue
            raise
        _working[kind] = model
        return result
    raise AgentError(
        f"None of these models are available on your Groq account: {', '.join(tried)}. "
        f"Set GROQ_CHAT_MODEL or GROQ_WHISPER_MODEL in .env (see console.groq.com/docs/models). Last error: {last}"
    )


def active_models() -> dict:
    """The models actually in use, for reports and the settings page."""
    return {"chat": _working.get("chat", config.CHAT_MODEL), "speech": _working.get("speech", config.WHISPER_MODEL)}


# ---------------------------------------------------------------- client and speech-to-text
def get_client(api_key: Optional[str] = None) -> Groq:
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise AgentError("GROQ_API_KEY is not set. Add it to a .env file or enter it in the sidebar.")
    return Groq(api_key=key, timeout=config.API_TIMEOUT_S, max_retries=config.API_MAX_RETRIES)


def transcribe(client, audio_bytes: bytes, filename: str) -> str:
    """Convert audio to text with Whisper."""
    try:
        result = _with_model_fallback(
            "speech", lambda model: client.audio.transcriptions.create(model=model, file=(filename, audio_bytes))
        )
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError(f"Transcription failed: {exc}") from exc
    text = (getattr(result, "text", "") or "").strip()
    if not text:
        raise AgentError("No speech was detected in the audio.")
    return text


# ---------------------------------------------------------------- parsing and validation
def parse_json_basic(raw: str) -> dict:
    """Baseline parser: strip code fences, then json.loads the whole reply."""
    text = raw.replace("```json", "").replace("```", "").strip()
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("JSON is not an object")
    return obj


def parse_json_tolerant(raw: str) -> dict:
    """Find the first JSON object in the reply, even if the model added text around it."""
    text = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in the reply")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("JSON is not an object")
    return obj


def check_schema(parsed: dict) -> list[str]:
    """Return a list of problems with a parsed reply. An empty list means it is valid."""
    problems = [f"missing key: {k}" for k in REQUIRED_KEYS if k not in parsed]
    if problems:
        return problems
    if parsed["intent_type"] not in config.INTENTS:
        problems.append(f"intent_type not allowed: {parsed['intent_type']!r}")
    if parsed["urgency"] not in config.URGENCY_LEVELS:
        problems.append(f"urgency not allowed: {parsed['urgency']!r}")
    if parsed["sentiment"] not in config.SENTIMENTS:
        problems.append(f"sentiment not allowed: {parsed['sentiment']!r}")
    score = parsed["lead_score"]
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        problems.append(f"lead_score not an integer 0-100: {score!r}")
    if not isinstance(parsed["tags"], list):
        problems.append("tags is not a list")
    return problems


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in ("", "null", "none", "n/a") else text


def normalize(raw: dict) -> dict:
    """Coerce a model reply into a safe record: allowed values only, score clamped, tags as a list."""
    intent = str(raw.get("intent_type", "other")).strip().lower().replace(" ", "_")
    urgency = str(raw.get("urgency", "Medium")).strip().capitalize()
    sentiment = str(raw.get("sentiment", "Neutral")).strip().capitalize()

    try:
        score = int(round(float(raw.get("lead_score", 0))))
    except (TypeError, ValueError):
        score = 0

    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split(",")
    tags = [str(t).strip().lstrip("#") for t in tags if str(t).strip()]

    return {
        "caller_name": _clean(raw.get("caller_name")),
        "callback_number": _clean(raw.get("callback_number")),
        "intent_type": intent if intent in config.INTENTS else "other",
        "course_interest": _clean(raw.get("course_interest")),
        "urgency": urgency if urgency in config.URGENCY_LEVELS else "Medium",
        "sentiment": sentiment if sentiment in config.SENTIMENTS else "Neutral",
        "lead_score": max(0, min(100, score)),
        "lead_score_reason": _clean(raw.get("lead_score_reason")) or "",
        "summary": _clean(raw.get("summary")) or "",
        "suggested_reply": _clean(raw.get("suggested_reply")) or "",
        "tags": tags,
    }


# ---------------------------------------------------------------- extraction
@dataclass
class Extraction:
    """Everything measured about one extraction, used by the evaluation harness."""

    record: Optional[dict] = None
    raw_text: str = ""
    first_json_ok: bool = False
    first_schema_ok: bool = False
    first_problems: list = field(default_factory=list)
    attempts: int = 0
    latency_s: float = 0.0
    error: Optional[str] = None
    error_type: Optional[str] = None


def _chat(client, cfg: dict, transcript: str) -> str:
    messages = [
        {"role": "system", "content": cfg["system"]},
        {"role": "user", "content": transcript},
    ]

    def request(model: str) -> str:
        kwargs = dict(model=model, temperature=0, messages=messages)
        if cfg["json_mode"]:
            try:
                resp = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
            except Exception as exc:
                # JSON mode can reject a reply it cannot validate. Fall back to a plain request.
                text = str(exc).lower()
                if _model_missing(exc) or ("json" not in text and "response_format" not in text):
                    raise
                resp = client.chat.completions.create(**kwargs)
        else:
            resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    return _with_model_fallback("chat", request)


def extract_lead_detailed(client, transcript: str, prompt_version: str = DEFAULT_PROMPT) -> Extraction:
    """Run extraction and record how it went, without raising."""
    cfg = PROMPTS[prompt_version]
    parse = parse_json_tolerant if cfg["tolerant_parse"] else parse_json_basic
    result = Extraction()
    started = time.perf_counter()

    for attempt in range(1, 2 + cfg["retries"]):
        result.attempts = attempt
        try:
            raw = _chat(client, cfg, transcript)
        except Exception as exc:  # network error, timeout, rate limit after SDK retries, bad request
            result.error, result.error_type = f"{type(exc).__name__}: {exc}", "api_error"
            break

        result.raw_text = raw
        try:
            parsed = parse(raw)
        except Exception as exc:
            result.error, result.error_type = f"Invalid JSON: {exc}", "invalid_json"
            continue

        problems = check_schema(parsed)
        if attempt == 1:
            result.first_json_ok, result.first_schema_ok, result.first_problems = True, not problems, problems
        result.record = normalize(parsed) if cfg["normalize"] else parsed
        result.error = result.error_type = None
        break

    result.latency_s = time.perf_counter() - started
    return result


def extract_lead(client, transcript: str, prompt_version: str = DEFAULT_PROMPT) -> dict:
    """Return a validated lead record or raise AgentError."""
    if not transcript or not transcript.strip():
        raise AgentError("The transcript is empty.")
    outcome = extract_lead_detailed(client, transcript, prompt_version)
    if outcome.record is None:
        raise AgentError(f"Could not analyse the call. {outcome.error}")
    return outcome.record
