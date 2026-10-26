"""Central configuration. Values can be overridden with environment variables or a .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "calls.db"))
CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# Groq retires models from time to time. If the configured model no longer exists, these are
# tried in order and the first one that works is used for the rest of the session.
CHAT_FALLBACKS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
SPEECH_FALLBACKS = ["whisper-large-v3-turbo", "whisper-large-v3"]

API_TIMEOUT_S = float(os.getenv("API_TIMEOUT_S", "30"))
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))

# Leads at or above this score are treated as high priority.
HIGH_PRIORITY_SCORE = 70

INTENTS = [
    "admission",
    "fee_inquiry",
    "placement_inquiry",
    "scheme_eligibility",
    "complaint",
    "general_query",
    "other",
]
URGENCY_LEVELS = ["High", "Medium", "Low"]
SENTIMENTS = ["Positive", "Neutral", "Frustrated"]
STATUSES = ["New", "Contacted", "Converted", "Closed"]
