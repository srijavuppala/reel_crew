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

# Two Gemini backends exist and the key prefix does NOT tell them apart -- an
# "AQ." key may be either an AI Studio key or an Agent Platform express key.
# So the backend is configurable, defaults to AI Studio, and falls back to the
# other endpoint once at runtime if the first returns PERMISSION_DENIED.
_VERTEX_ENV = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower()
PREFER_VERTEX = _VERTEX_ENV in ("1", "true", "yes")

GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"

# The agent runs end to end without a key; Gemini upgrades parsing and narration.
GEMINI_ENABLED = bool(GOOGLE_API_KEY) or (PREFER_VERTEX and bool(GCP_PROJECT))

# Set once the first successful call proves which backend this key belongs to.
_working_backend: str | None = None


def gemini_backend() -> str:
    """Which backend LLM calls will use. Reflects what actually worked, once known."""
    if not GEMINI_ENABLED:
        return "disabled"
    if _working_backend:
        return _working_backend
    return "agent-platform" if PREFER_VERTEX else "ai-studio"


# Cached: a client that goes out of scope is closed, and the next call on it
# fails with "Cannot send a request, as the client has been closed".
_clients: dict[bool, object] = {}


def _client(vertex: bool):
    from google import genai

    if vertex not in _clients:
        if vertex:
            _clients[vertex] = (
                genai.Client(vertexai=True, api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY
                else genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
            )
        else:
            _clients[vertex] = genai.Client(api_key=GOOGLE_API_KEY)
    return _clients[vertex]


def get_genai_client():
    """Client for the backend currently believed to work."""
    return _client(gemini_backend() == "agent-platform")


def gemini_generate(system_instruction: str, contents: str, response_schema=None,
                    temperature: float = 0.0) -> str:
    """Call Gemini and return raw text, trying the other backend once on 403.

    Centralising the fallback here means parse and narrate never have to know
    which endpoint the key belongs to.
    """
    global _working_backend
    from google.genai import types

    cfg = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        temperature=temperature,
    )
    if response_schema is not None:
        cfg.response_schema = response_schema

    order = [PREFER_VERTEX, not PREFER_VERTEX] if _working_backend is None \
        else [_working_backend == "agent-platform"]

    last: Exception | None = None
    for vertex in order:
        try:
            resp = _client(vertex).models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=cfg)
            _working_backend = "agent-platform" if vertex else "ai-studio"
            return resp.text or ""
        except Exception as exc:  # noqa: BLE001
            last = exc
            if "PERMISSION_DENIED" not in str(exc) and "403" not in str(exc):
                raise
    raise last  # type: ignore[misc]


# ---------------------------------------------------------------- ClickHouse
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
            session_id=f"rc-{uuid.uuid4().hex[:12]}",
        )
        _local.client = client
    return client
