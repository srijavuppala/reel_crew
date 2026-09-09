"""Blocking client for the official mcp-clickhouse stdio server.

The web API stays synchronous at the query boundary, while every production
query crosses the MCP protocol and is executed by ClickHouse's official server.

A stdio server is one process speaking one conversation at a time, so a single
client serialises every request in the app: six concurrent searches measured
18.3s wall clock against 3.9s for one. Requests are therefore handed to a small
pool of servers. Processes spawn on first use, so a single-user session still
pays for exactly one.
"""
from __future__ import annotations

import atexit
import contextlib
import json
import os
import queue
import re
import select
import subprocess
import sys
import threading
from typing import Any

# A query that has not answered in this long is not slow, it is wedged: the
# ranking queries return in well under a second.
READ_TIMEOUT = float(os.getenv("MCP_READ_TIMEOUT", "90"))
POOL_SIZE = max(1, int(os.getenv("MCP_POOL_SIZE", "3")))


class ClickHouseMCP:
    """One mcp-clickhouse subprocess. The pool owns access; do not share directly."""

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

    def _readline(self) -> str:
        """Read one line, giving up rather than blocking a worker indefinitely.

        The server writes newline-delimited JSON, so a ready fd means a whole
        line is on its way; select only guards against nothing arriving at all.
        """
        stdout = self._process.stdout if self._process else None
        if stdout is None:
            raise RuntimeError("mcp-clickhouse process is unavailable")
        ready, _, _ = select.select([stdout], [], [], READ_TIMEOUT)
        if not ready:
            self.close()
            raise TimeoutError(f"mcp-clickhouse did not respond within {READ_TIMEOUT:g}s")
        return stdout.readline()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._process or not self._process.stdout:
            raise RuntimeError("mcp-clickhouse process is unavailable")
        self._id += 1
        request_id = self._id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            line = self._readline()
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


class _Pool:
    """Hands out servers, creating at most POOL_SIZE of them.

    Each holds ~110 MB resident once started, which is why the size is modest
    and configurable rather than one server per request.
    """

    def __init__(self, size: int) -> None:
        self._free: queue.Queue[ClickHouseMCP] = queue.Queue()
        for _ in range(size):
            self._free.put(ClickHouseMCP())   # process spawns lazily on first query
        atexit.register(self.close)

    @contextlib.contextmanager
    def borrow(self):
        client = self._free.get()
        try:
            yield client
        finally:
            self._free.put(client)

    def close(self) -> None:
        while True:
            try:
                self._free.get_nowait().close()
            except queue.Empty:
                return


_POOL = _Pool(POOL_SIZE)


def run_query(sql: str) -> tuple[list[str], list[list[Any]]]:
    with _POOL.borrow() as client:
        payload = client.query(sql)
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
