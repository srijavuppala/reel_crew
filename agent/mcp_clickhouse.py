"""Blocking client for the official mcp-clickhouse stdio server.

The web API stays synchronous at the query boundary, while every production
query crosses the MCP protocol and is executed by ClickHouse's official server.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import sys
import threading
from typing import Any


class ClickHouseMCP:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._id = 0
        atexit.register(self.close)

    def _start(self) -> None:
        if self._process and self._process.poll() is None:
            return
        env = os.environ.copy()
        env.setdefault("CLICKHOUSE_MCP_SERVER_TRANSPORT", "stdio")
        env.setdefault("CLICKHOUSE_ALLOW_WRITE_ACCESS", "false")
        self._process = subprocess.Popen(
            [sys.executable, "-m", "mcp_clickhouse.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
            env=env,
        )
        self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "reel-crew", "version": "1.0.0"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, message: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("mcp-clickhouse process is unavailable")
        self._process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self._process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._process or not self._process.stdout:
            raise RuntimeError("mcp-clickhouse process is unavailable")
        self._id += 1
        request_id = self._id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError("mcp-clickhouse stopped before responding")
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise RuntimeError(response["error"].get("message", str(response["error"])))
            return response.get("result", {})

    def query(self, sql: str) -> dict[str, Any]:
        with self._lock:
            self._start()
            try:
                result = self._request("tools/call", {
                    "name": "run_query", "arguments": {"query": sql}
                })
            except (BrokenPipeError, RuntimeError):
                self.close()
                self._start()
                result = self._request("tools/call", {
                    "name": "run_query", "arguments": {"query": sql}
                })
        if result.get("isError"):
            raise RuntimeError("mcp-clickhouse query failed")
        content = result.get("content") or []
        if not content or "text" not in content[0]:
            raise RuntimeError("mcp-clickhouse returned no query payload")
        return json.loads(content[0]["text"])

    def close(self) -> None:
        process, self._process = self._process, None
        if process and process.poll() is None:
            process.terminate()


_MCP = ClickHouseMCP()


def run_query(sql: str) -> tuple[list[str], list[list[Any]]]:
    payload = _MCP.query(sql)
    return payload.get("columns", []), payload.get("rows", [])


def render_query(sql: str, params: dict[str, Any]) -> str:
    """Render ClickHouse typed placeholders after converting values to literals."""
    def literal(value: Any) -> str:
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return "[" + ",".join(literal(item) for item in value) + "]"
        return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in params:
            raise ValueError(f"Missing query parameter: {name}")
        return literal(params[name])

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*):[^}]+\}", replace, sql)
