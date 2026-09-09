"""Runtime configuration and the shared ClickHouse client."""
from __future__ import annotations

import os
import threading
import uuid
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

# Gemini Enterprise Agent Platform (Vertex AI) vs the AI Studio Gemini API.
# Agent Platform express keys start with "AQ." and must go to aiplatform.googleapis.com;
# AI Studio keys start with "AIza" and go to generativelanguage.googleapis.com.
# Sending either to the other endpoint fails with a confusing 403, so detect it.
_VERTEX_ENV = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower()
USE_VERTEX = (_VERTEX_ENV in ("1", "true", "yes")
              or (not _VERTEX_ENV and GOOGLE_API_KEY.startswith("AQ.")))

GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"

# The agent runs end to end without a key; Gemini upgrades parsing and narration.
GEMINI_ENABLED = bool(GOOGLE_API_KEY) or (USE_VERTEX and bool(GCP_PROJECT))


def gemini_backend() -> str:
    """Human-readable name of the backend the LLM calls will use."""
    if not GEMINI_ENABLED:
        return "disabled"
    if USE_VERTEX:
        return "gemini-enterprise-agent-platform" + ("" if GOOGLE_API_KEY else " (ADC)")
    return "ai-studio"


def get_genai_client():
    """Build a google-genai client for whichever Gemini backend is configured.

    Three supported shapes:
      * Agent Platform express key  -> Client(vertexai=True, api_key="AQ...")
      * Agent Platform via ADC      -> Client(vertexai=True, project=..., location=...)
      * AI Studio key               -> Client(api_key="AIza...")
    """
    from google import genai

    if USE_VERTEX:
        if GOOGLE_API_KEY:
            return genai.Client(vertexai=True, api_key=GOOGLE_API_KEY)
        return genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    return genai.Client(api_key=GOOGLE_API_KEY)


# One client per thread. A single shared client raises
# "Attempt to execute concurrent queries within the same session" as soon as
# FastAPI serves a sync endpoint (threadpool) and an async one at the same time,
# so each thread gets its own client and its own ClickHouse session id.
_local = threading.local()


def get_client():
    """Return this thread's ClickHouse client. Called at runtime on every request."""
    client = getattr(_local, "client", None)
    if client is None:
        client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD,
            database=CH_DATABASE,
            secure=CH_SECURE,
            connect_timeout=15,
            send_receive_timeout=120,
            session_id=f"btl-{uuid.uuid4().hex[:12]}",
        )
        _local.client = client
    return client
