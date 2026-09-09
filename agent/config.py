"""Runtime configuration and the shared ClickHouse client."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "8443"))
CH_USER = os.getenv("CLICKHOUSE_USER", "default")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CH_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")
CH_SECURE = os.getenv("CLICKHOUSE_SECURE", "true").lower() == "true"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# The agent runs end to end without a key; Gemini upgrades parsing and narration.
GEMINI_ENABLED = bool(GOOGLE_API_KEY)


@lru_cache(maxsize=1)
def get_client():
    """Return a pooled ClickHouse client. Called at runtime on every request."""
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
        secure=CH_SECURE,
        connect_timeout=15,
        send_receive_timeout=120,
    )
